import logging
import re

import bleach
from django.contrib import messages
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views import View

from pretix.base.i18n import language
from pretix.base.services.mail import prefix_subject
from pretix.base.services.placeholders import get_sample_context
from pretix.base.templatetags.rich_text import markdown_compile_email
from pretix.control.permissions import OrganizerPermissionRequiredMixin
from pretix.control.views.event import EventSettingsFormView, EventSettingsViewMixin
from pretix.control.views.organizer import OrganizerSettingsFormView
from pretix.helpers.format import SafeFormatter, format_map

from .forms import EMAIL_TYPES, MAIL_KEY_MAP, EventEmailContentForm, OrganizerEmailTemplatesForm

logger = logging.getLogger(__name__)

# Maps our emailtemplates_* field names to the same base context parameters
# that MailSettingsForm.base_context uses for the equivalent mail_* fields.
_ORGANIZER_PREVIEW_BASE_CONTEXT = {
    'emailtemplates_subject_order_placed': ['event', 'order', 'payments'],
    'emailtemplates_text_order_placed': ['event', 'order', 'payments'],
    'emailtemplates_subject_order_paid': ['event', 'order', 'payment_info'],
    'emailtemplates_text_order_paid': ['event', 'order', 'payment_info'],
    'emailtemplates_subject_order_free': ['event', 'order'],
    'emailtemplates_text_order_free': ['event', 'order'],
    'emailtemplates_subject_resend_link': ['event', 'order'],
    'emailtemplates_text_resend_link': ['event', 'order'],
    'emailtemplates_subject_order_changed': ['event', 'order'],
    'emailtemplates_text_order_changed': ['event', 'order'],
    'emailtemplates_subject_order_expire_warning': ['event', 'order'],
    'emailtemplates_text_order_expire_warning': ['event', 'order'],
    'emailtemplates_subject_order_payment_failed': ['event', 'order'],
    'emailtemplates_text_order_payment_failed': ['event', 'order'],
    'emailtemplates_subject_waiting_list': ['event', 'waiting_list_entry', 'waiting_list_voucher'],
    'emailtemplates_text_waiting_list': ['event', 'waiting_list_entry', 'waiting_list_voucher'],
    'emailtemplates_subject_order_canceled': ['event', 'order'],
    'emailtemplates_text_order_canceled': ['event', 'order'],
    'emailtemplates_subject_order_custom_mail': ['event', 'order'],
    'emailtemplates_text_order_custom_mail': ['event', 'order'],
    'emailtemplates_subject_download_reminder': ['event', 'order'],
    'emailtemplates_text_download_reminder': ['event', 'order'],
    'emailtemplates_subject_order_approved': ['event', 'order'],
    'emailtemplates_text_order_approved': ['event', 'order'],
    'emailtemplates_subject_order_denied': ['event', 'order'],
    'emailtemplates_text_order_denied': ['event', 'order'],
}

# Hardcoded sample values for organizer-level preview (no event available)
_ORGANIZER_SAMPLE_VALUES = {
    'event': 'Sample Event',
    'event_slug': 'sample-event',
    'code': 'ABCDE',
    'order': 'ABCDE',
    'total': '42.00',
    'total_with_currency': 'EUR 42.00',
    'currency': 'EUR',
    'expire_date': '2026-04-30',
    'url': 'https://example.pretix.eu/sample/event/order/ABCDE/secret/',
    'url_cancel': 'https://example.pretix.eu/sample/event/order/ABCDE/secret/cancel/',
    'url_info_change': 'https://example.pretix.eu/sample/event/order/ABCDE/secret/info/',
    'url_products_change': 'https://example.pretix.eu/sample/event/order/ABCDE/secret/change/',
    'invoice_name': 'John Doe',
    'invoice_company': 'Example Corp',
    'name': 'John Doe',
    'payment_info': '(payment details)',
    'comment': '',
    'payments': '',
    'waiting_list_entry': '',
    'waiting_list_voucher': '',
    'pending_sum': '10.00',
}


class OrganizerEmailTemplatesView(OrganizerSettingsFormView):
    """
    Organizer-level view for managing email template defaults.
    Stores values under emailtemplates_subject_* / emailtemplates_text_* in organizer.settings.
    """
    form_class = OrganizerEmailTemplatesForm
    template_name = 'pretix_organizeremailtemplates/organizer_settings.html'
    permission = 'can_change_organizer_settings'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['mail_preview_url'] = reverse(
            'plugins:pretix_organizeremailtemplates:organizer.settings.preview',
            kwargs={'organizer': self.request.organizer.slug},
        )
        return ctx

    def get_success_url(self):
        return reverse(
            'plugins:pretix_organizeremailtemplates:organizer.settings',
            kwargs={'organizer': self.request.organizer.slug},
        )


class OrganizerEmailTemplatesPreview(OrganizerPermissionRequiredMixin, View):
    """
    AJAX preview endpoint for the organizer email templates form.
    Accepts emailtemplates_subject_* / emailtemplates_text_* field names and
    renders a preview using hardcoded sample values (no event available at org level).
    """
    permission = 'can_change_organizer_settings'

    class _SafeDict(dict):
        """Returns '{key}' for missing keys so unknown placeholders pass through."""
        def __missing__(self, key):
            return '{' + key + '}'

    @cached_property
    def supported_locale(self):
        locales = {}
        from django.conf import settings as django_settings
        for idx, val in enumerate(django_settings.LANGUAGES):
            if val[0] in self.request.organizer.settings.locales:
                locales[str(idx)] = val[0]
        return locales

    def placeholders(self):
        ctx = {}
        for k, v in _ORGANIZER_SAMPLE_VALUES.items():
            if v:
                ctx[k] = '<span class="placeholder" title="{title}">{val}</span>'.format(
                    title=_('This value will be replaced based on dynamic parameters.'),
                    val=v,
                )
            else:
                ctx[k] = ''
        return self._SafeDict(ctx)

    def post(self, request, *args, **kwargs):
        preview_item = request.POST.get('item', '')
        if preview_item not in _ORGANIZER_PREVIEW_BASE_CONTEXT:
            return HttpResponseBadRequest(_('invalid item'))

        regex = r'^' + re.escape(preview_item) + r'_(?P<idx>[\d]+)$'
        msgs = {}
        placeholders = self.placeholders()

        for k, v in request.POST.items():
            matched = re.search(regex, k)
            if matched is None:
                continue
            idx = matched.group('idx')
            if idx not in self.supported_locale:
                continue
            with language(self.supported_locale[idx], self.request.organizer.settings.region):
                if preview_item.startswith('emailtemplates_subject_'):
                    msgs[self.supported_locale[idx]] = prefix_subject(
                        self.request.organizer,
                        format_map(bleach.clean(v), placeholders),
                        highlight=True,
                    )
                else:
                    msgs[self.supported_locale[idx]] = format_map(
                        markdown_compile_email(format_map(v, placeholders)),
                        placeholders,
                        mode=SafeFormatter.MODE_RICH_TO_HTML,
                    )

        return JsonResponse({'item': preview_item, 'msgs': msgs})


class EventEmailContentView(EventSettingsViewMixin, EventSettingsFormView):
    """
    Event-level view for managing email content with lock/unlock support.
    """
    form_class = EventEmailContentForm
    template_name = 'pretix_organizeremailtemplates/event_settings.html'
    permission = 'can_change_event_settings'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organizer'] = self.request.organizer
        return kwargs

    def get_success_url(self):
        return reverse(
            'plugins:pretix_organizeremailtemplates:event.settings',
            kwargs={
                'organizer': self.request.organizer.slug,
                'event': self.request.event.slug,
            },
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['is_locked'] = bool(
            self.request.event.settings.get('emailtemplates_content_locked', as_type=bool)
        )
        ctx['organizer_has_templates'] = self._organizer_has_templates()
        ctx['mail_preview_url'] = reverse(
            'control:event.settings.mail.preview',
            kwargs={
                'organizer': self.request.organizer.slug,
                'event': self.request.event.slug,
            },
        )
        return ctx

    def _organizer_has_templates(self):
        """Return True if the organizer has any email template values set."""
        org_settings = self.request.organizer.settings
        for email_type, _label in EMAIL_TYPES:
            if org_settings.get('emailtemplates_subject_%s' % email_type):
                return True
            if org_settings.get('emailtemplates_text_%s' % email_type):
                return True
        return False

    def get(self, request, *args, **kwargs):
        # Allow the lock-banner "Unlock for This Event" link to trigger unlock via GET
        if request.GET.get('action') == 'unlock':
            org_settings = request.organizer.settings
            for email_type, _label in EMAIL_TYPES:
                subject_key, text_key = MAIL_KEY_MAP[email_type]
                org_subject = org_settings.get('emailtemplates_subject_%s' % email_type)
                org_text = org_settings.get('emailtemplates_text_%s' % email_type)
                if org_subject:
                    request.event.settings.set(subject_key, org_subject)
                if org_text:
                    request.event.settings.set(text_key, org_text)
            request.event.settings.set('emailtemplates_content_locked', False)
            request.event.settings.flush()
            messages.success(request, _('Email content has been unlocked for event-level editing.'))
            return redirect(self.get_success_url())
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')

        if action == 'lock':
            for email_type, _label in EMAIL_TYPES:
                subject_key, text_key = MAIL_KEY_MAP[email_type]
                request.event.settings.delete(subject_key)
                request.event.settings.delete(text_key)
            request.event.settings.set('emailtemplates_content_locked', True)
            request.event.settings.flush()
            messages.success(request, _('Email content has been locked to organizer templates.'))
            return redirect(self.get_success_url())

        if action == 'unlock':
            org_settings = request.organizer.settings
            for email_type, _label in EMAIL_TYPES:
                subject_key, text_key = MAIL_KEY_MAP[email_type]
                org_subject = org_settings.get('emailtemplates_subject_%s' % email_type)
                org_text = org_settings.get('emailtemplates_text_%s' % email_type)
                if org_subject:
                    request.event.settings.set(subject_key, org_subject)
                if org_text:
                    request.event.settings.set(text_key, org_text)
            request.event.settings.set('emailtemplates_content_locked', False)
            request.event.settings.flush()
            messages.success(request, _('Email content has been unlocked for event-level editing.'))
            return redirect(self.get_success_url())

        return super().post(request, *args, **kwargs)
