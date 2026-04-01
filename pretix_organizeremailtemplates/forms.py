"""
Pattern notes (2026-03-31):
  - Body fields use I18nMarkdownTextarea (same as pretix native MailSettingsForm).
  - EventEmailContentForm inherits FormPlaceholderMixin and calls _set_field_placeholders
    for each mail_* field using the same base_context map as MailSettingsForm. This gives
    dynamic help_text with clickable placeholder buttons and per-locale sample values.
  - OrganizerEmailTemplatesForm uses a generic static placeholder list via
    format_placeholders_help_text({name: ''}) since no event is available at organizer scope.
  - Preview: event form points to the native control:event.settings.mail.preview URL (works
    because field names match MailSettingsForm.base_context). Organizer form points to our
    custom OrganizerEmailTemplatesPreview view in views.py.
"""
import logging

from django import forms
from django.db.models import Prefetch
from django.utils import translation
from django.utils.translation import gettext_lazy as _
from i18nfield.forms import I18nFormField, I18nTextInput
from i18nfield.strings import LazyI18nString

from pretix.base.forms import I18nMarkdownTextarea, SettingsForm
from pretix.base.forms.widgets import format_placeholders_help_text
from pretix.base.services.placeholders import FormPlaceholderMixin
from pretix.base.settings import DEFAULTS
from pretix.control.forms.event import MailSettingsForm

logger = logging.getLogger(__name__)

EMAIL_TYPES = [
    ('order_placed', _('Placed order')),
    ('order_paid', _('Paid order')),
    ('order_free', _('Free order')),
    ('resend_link', _('Resend link')),
    ('order_changed', _('Order changed')),
    ('order_expire_warning', _('Payment reminder')),
    ('order_payment_failed', _('Payment failed')),
    ('waiting_list', _('Waiting list notification')),
    ('order_canceled', _('Order canceled')),
    ('order_custom_mail', _('Order custom mail')),
    ('download_reminder', _('Download reminder')),
    ('order_approved', _('Order approved')),
    ('order_denied', _('Order denied')),
]

# The native pretix mail_* key names for each email type
MAIL_KEY_MAP = {
    'order_placed': ('mail_subject_order_placed', 'mail_text_order_placed'),
    'order_paid': ('mail_subject_order_paid', 'mail_text_order_paid'),
    'order_free': ('mail_subject_order_free', 'mail_text_order_free'),
    'resend_link': ('mail_subject_resend_link', 'mail_text_resend_link'),
    'order_changed': ('mail_subject_order_changed', 'mail_text_order_changed'),
    'order_expire_warning': ('mail_subject_order_expire_warning', 'mail_text_order_expire_warning'),
    'order_payment_failed': ('mail_subject_order_payment_failed', 'mail_text_order_payment_failed'),
    'waiting_list': ('mail_subject_waiting_list', 'mail_text_waiting_list'),
    'order_canceled': ('mail_subject_order_canceled', 'mail_text_order_canceled'),
    'order_custom_mail': ('mail_subject_order_custom_mail', 'mail_text_order_custom_mail'),
    'download_reminder': ('mail_subject_download_reminder', 'mail_text_download_reminder'),
    'order_approved': ('mail_subject_order_approved', 'mail_text_order_approved'),
    'order_denied': ('mail_subject_order_denied', 'mail_text_order_denied'),
}

# Generic placeholders shown on the organizer form (no event available for dynamic lookup)
_ORGANIZER_PLACEHOLDER_NAMES = [
    'code', 'currency', 'event', 'event_slug', 'expire_date',
    'invoice_company', 'invoice_name', 'name', 'order',
    'total', 'total_with_currency', 'url',
]
_ORGANIZER_PLACEHOLDER_HELP = format_placeholders_help_text(
    {name: '' for name in _ORGANIZER_PLACEHOLDER_NAMES}
)


def apply_organizer_templates_to_event(organizer, event):
    """
    Copy organizer emailtemplates_* values into event mail_* keys so pretix's
    mail service picks them up. Call this whenever an event is locked or when
    organizer templates are updated.
    """
    for email_type, _label in EMAIL_TYPES:
        subject_key, text_key = MAIL_KEY_MAP[email_type]
        org_subject = organizer.settings.get('emailtemplates_subject_%s' % email_type)
        org_text = organizer.settings.get('emailtemplates_text_%s' % email_type)
        if org_subject:
            event.settings.set(subject_key, org_subject)
        else:
            event.settings.delete(subject_key)
        if org_text:
            event.settings.set(text_key, org_text)
        else:
            event.settings.delete(text_key)
    event.settings.flush()


def _build_organizer_fields():
    """Return a dict of field definitions for OrganizerEmailTemplatesForm."""
    fields = {}
    for email_type, label in EMAIL_TYPES:
        fields['emailtemplates_subject_%s' % email_type] = I18nFormField(
            label=_('Subject — %(label)s') % {'label': label},
            required=False,
            widget=I18nTextInput,
        )
        fields['emailtemplates_text_%s' % email_type] = I18nFormField(
            label=_('Body — %(label)s') % {'label': label},
            required=False,
            widget=I18nMarkdownTextarea,
            help_text=_ORGANIZER_PLACEHOLDER_HELP,
        )
    return fields


class OrganizerEmailTemplatesForm(SettingsForm):
    """
    Stores organizer-level email template defaults under emailtemplates_subject_*
    and emailtemplates_text_* keys in organizer.settings.

    Always renders inputs for English, German, and German (informal) regardless of
    which locales the organizer has globally enabled.
    """

    emailtemplates_auto_lock_new_events = forms.BooleanField(
        required=False,
        label=_('Automatically lock email content on newly activated events'),
        help_text=_('When this plugin is enabled on a new event, its email content will '
                    'automatically be locked to use these organizer templates.'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in _build_organizer_fields().items():
            if name not in self.fields:
                self.fields[name] = field
            # Apply locales to the field instance that is actually in the form
            live_field = self.fields[name]
            if hasattr(live_field, 'widget') and hasattr(live_field.widget, 'enabled_locales'):
                live_field.widget.enabled_locales = self.locales

        # Pre-fill with pretix defaults for any field not yet configured
        self._prefill_from_pretix_defaults()

    def _prefill_from_pretix_defaults(self):
        """
        For each emailtemplates_* field that the organizer hasn't set yet, inject
        the pretix default (from DEFAULTS['mail_*']) as the initial value, translated
        into each active locale so the multi-language inputs are all populated.
        """
        active_locales = self.locales or ['en']
        for email_type, _ in EMAIL_TYPES:
            pairs = [
                ('emailtemplates_subject_%s' % email_type, MAIL_KEY_MAP[email_type][0]),
                ('emailtemplates_text_%s' % email_type,    MAIL_KEY_MAP[email_type][1]),
            ]
            for org_key, mail_key in pairs:
                # Skip if the organizer already has a value stored
                if self.obj.settings.get(org_key):
                    continue
                pretix_default = DEFAULTS.get(mail_key, {}).get('default')
                if not pretix_default:
                    continue
                # Build a per-locale dict so each language input is populated
                locale_dict = {}
                for locale in active_locales:
                    # de-informal shares translations with de
                    trans_locale = locale.replace('-informal', '')
                    with translation.override(trans_locale):
                        locale_dict[locale] = str(pretix_default)
                if org_key in self.fields:
                    self.fields[org_key].initial = LazyI18nString(locale_dict)


# Inject class-level field declarations so SettingsForm's HierarkeyForm
# can discover them for the initial population from settings.
for _name, _field in _build_organizer_fields().items():
    OrganizerEmailTemplatesForm.base_fields[_name] = _field


class EventEmailContentForm(FormPlaceholderMixin, SettingsForm):
    """
    Stores event-level email content using the native pretix mail_subject_* /
    mail_text_* key names so pretix's mail service picks them up transparently.

    Also manages the emailtemplates_content_locked flag.
    """

    emailtemplates_content_locked = forms.BooleanField(
        required=False,
        label=_('Lock email content (use organizer templates)'),
    )

    def __init__(self, *args, **kwargs):
        self._organizer = kwargs.pop('organizer', None)
        super().__init__(*args, **kwargs)
        # Required by FormPlaceholderMixin._set_field_placeholders
        self.event = self.obj

        # Prefetch meta properties so meta_ placeholders resolve in _set_field_placeholders
        from django.db.models import Prefetch as _Prefetch
        from pretix.base.models import Event as _Event
        if isinstance(self.event, _Event):
            from django.db.models import prefetch_related_objects
            prefetch_related_objects([self.event.organizer], _Prefetch('meta_properties'))
            self.event.meta_values_cached = (
                self.event.meta_values.select_related('property').all()
            )

        is_locked = bool(self.obj.settings.get('emailtemplates_content_locked', as_type=bool))

        for email_type, label in EMAIL_TYPES:
            subject_key, text_key = MAIL_KEY_MAP[email_type]

            subject_field = I18nFormField(
                label=_('Subject — %(label)s') % {'label': label},
                required=False,
                widget=I18nTextInput,
            )
            text_field = I18nFormField(
                label=_('Body — %(label)s') % {'label': label},
                required=False,
                widget=I18nMarkdownTextarea,
            )

            if self.locales:
                subject_field.widget.enabled_locales = self.locales
                text_field.widget.enabled_locales = self.locales

            if is_locked:
                # Show organizer values as initial but make fields read-only
                if self._organizer:
                    org_subject = self._organizer.settings.get(
                        'emailtemplates_subject_%s' % email_type
                    )
                    org_text = self._organizer.settings.get(
                        'emailtemplates_text_%s' % email_type
                    )
                    subject_field.initial = org_subject
                    text_field.initial = org_text
                subject_field.widget.attrs = {'disabled': 'disabled'}
                text_field.widget.attrs = {'disabled': 'disabled'}

            self.fields[subject_key] = subject_field
            self.fields[text_key] = text_field

            # Add dynamic placeholder help_text using pretix's signal-based lookup
            if subject_key in MailSettingsForm.base_context:
                self._set_field_placeholders(
                    subject_key, MailSettingsForm.base_context[subject_key]
                )
            if text_key in MailSettingsForm.base_context:
                self._set_field_placeholders(
                    text_key,
                    MailSettingsForm.base_context[text_key],
                    rich=(text_key not in MailSettingsForm.plain_rendering),
                )

    def save(self):
        # Never save mail_* keys when locked — they are read from organizer via hierarkey cascade
        is_locked = self.cleaned_data.get('emailtemplates_content_locked', False)
        if is_locked:
            self.obj.settings.set('emailtemplates_content_locked', True)
        else:
            self.obj.settings.set('emailtemplates_content_locked', False)
            for email_type, _label in EMAIL_TYPES:
                subject_key, text_key = MAIL_KEY_MAP[email_type]
                if subject_key in self.cleaned_data:
                    val = self.cleaned_data[subject_key]
                    if val:
                        self.obj.settings.set(subject_key, val)
                    else:
                        self.obj.settings.delete(subject_key)
                if text_key in self.cleaned_data:
                    val = self.cleaned_data[text_key]
                    if val:
                        self.obj.settings.set(text_key, val)
                    else:
                        self.obj.settings.delete(text_key)
