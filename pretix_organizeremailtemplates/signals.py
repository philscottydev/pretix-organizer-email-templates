import logging

from django.dispatch import receiver
from django.urls import resolve, reverse
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from pretix.base.signals import event_copy_data
from pretix.control.signals import html_page_start, nav_event_settings, nav_organizer

logger = logging.getLogger(__name__)


@receiver(nav_organizer, dispatch_uid='organizeremailtemplates_nav_organizer')
def nav_organizer_receiver(sender, request=None, **kwargs):
    if not request.user.has_organizer_permission(
        request.organizer, 'can_change_organizer_settings', request=request
    ):
        return []
    url = resolve(request.path_info)
    return [{
        'label': _('Event email templates'),
        'url': reverse(
            'plugins:pretix_organizeremailtemplates:organizer.settings',
            kwargs={'organizer': request.organizer.slug},
        ),
        'icon': 'envelope',
        'active': url.namespace == 'plugins:pretix_organizeremailtemplates' and url.url_name == 'organizer.settings',
    }]


@receiver(nav_event_settings, dispatch_uid='organizeremailtemplates_nav_event_settings')
def nav_event_settings_receiver(sender, request=None, **kwargs):
    if not request.user.has_event_permission(
        request.organizer, request.event, 'can_change_event_settings', request=request
    ):
        return []
    url = resolve(request.path_info)
    return [{
        'label': _('Email content'),
        'url': reverse(
            'plugins:pretix_organizeremailtemplates:event.settings',
            kwargs={
                'organizer': request.organizer.slug,
                'event': request.event.slug,
            },
        ),
        'icon': 'envelope-o',
        'active': url.namespace == 'plugins:pretix_organizeremailtemplates' and url.url_name == 'event.settings',
    }]


@receiver(html_page_start, dispatch_uid='organizeremailtemplates_html_page_start')
def inject_lock_banner(sender, **kwargs):
    request = sender

    if not hasattr(request, 'event'):
        return ''
    if not request.path_info.endswith('/settings/email'):
        return ''
    if 'pretix_organizeremailtemplates' not in request.event.plugins:
        return ''

    is_locked = bool(request.event.settings.get('emailtemplates_content_locked', as_type=bool))
    organizer_url = reverse(
        'plugins:pretix_organizeremailtemplates:organizer.settings',
        kwargs={'organizer': request.organizer.slug},
    )
    event_settings_url = reverse(
        'plugins:pretix_organizeremailtemplates:event.settings',
        kwargs={'organizer': request.organizer.slug, 'event': request.event.slug},
    )

    if is_locked and _organizer_has_templates(request.organizer):
        # LOCKED banner (existing)
        return mark_safe(format_html(
            '''
            <div class="alert alert-info alert-dismissible" role="alert" style="margin-bottom:20px;">
                <button type="button" class="close" data-dismiss="alert" aria-label="Close">
                    <span aria-hidden="true">&times;</span>
                </button>
                <h4><i class="fa fa-lock"></i> {heading}</h4>
                <p>{body}</p>
                <p>
                    <a href="{organizer_url}" class="btn btn-sm btn-default" target="_blank">
                        <i class="fa fa-external-link"></i> {btn_organizer}
                    </a>
                    &nbsp;
                    <a href="{unlock_url}" class="btn btn-sm btn-warning">
                        <i class="fa fa-unlock"></i> {btn_unlock}
                    </a>
                </p>
            </div>
            ''',
            heading=_('Email content is managed at organizer level'),
            body=_('This event inherits email templates from the organizer. '
                   'Changes made on this page will be ignored while content is locked.'),
            organizer_url=organizer_url,
            unlock_url=event_settings_url + '?action=unlock',
            btn_organizer=_('Go to Organizer Email Templates'),
            btn_unlock=_('Unlock for This Event'),
        ))

    if not is_locked and _organizer_has_templates(request.organizer):
        # UNLOCKED banner (new) — suggest organizer templates are available
        return mark_safe(format_html(
            '''
            <div class="alert alert-warning alert-dismissible" role="alert" style="margin-bottom:20px;">
                <button type="button" class="close" data-dismiss="alert" aria-label="Close">
                    <span aria-hidden="true">&times;</span>
                </button>
                <h4><i class="fa fa-unlock"></i> {heading}</h4>
                <p>{body}</p>
                <p>
                    <a href="{lock_url}" class="btn btn-sm btn-primary">
                        <i class="fa fa-lock"></i> {btn_lock}
                    </a>
                    &nbsp;
                    <a href="{organizer_url}" class="btn btn-sm btn-default" target="_blank">
                        <i class="fa fa-external-link"></i> {btn_organizer}
                    </a>
                </p>
            </div>
            ''',
            heading=_('Email content is managed per-event'),
            body=_('Organizer-level email templates are available. '
                   'You can lock this event to use them instead of the per-event settings below.'),
            lock_url=event_settings_url + '?action=lock',
            organizer_url=organizer_url,
            btn_lock=_('Lock to Organizer Templates'),
            btn_organizer=_('View Organizer Templates'),
        ))

    return ''


def _organizer_has_templates(organizer):
    from .forms import EMAIL_TYPES
    for email_type, _label in EMAIL_TYPES:
        if organizer.settings.get('emailtemplates_subject_%s' % email_type):
            return True
        if organizer.settings.get('emailtemplates_text_%s' % email_type):
            return True
    return False


@receiver(event_copy_data, dispatch_uid='organizeremailtemplates_event_copy_data')
def on_event_copy_data(sender, other, **kwargs):
    """
    sender = new event, other = source event.
    If source was locked, apply auto-lock to the new event too.
    """
    from .forms import apply_organizer_templates_to_event, EMAIL_TYPES
    source_locked = bool(other.settings.get('emailtemplates_content_locked', as_type=bool))
    if not source_locked:
        return
    # Only lock if organizer has templates
    organizer = sender.organizer
    has_templates = any(
        organizer.settings.get('emailtemplates_subject_%s' % et)
        or organizer.settings.get('emailtemplates_text_%s' % et)
        for et, _label in EMAIL_TYPES
    )
    if not has_templates:
        return
    apply_organizer_templates_to_event(sender.organizer, sender)
    sender.settings.set('emailtemplates_content_locked', True)
    # flush is called inside apply_organizer_templates_to_event
    logger.debug('organizeremailtemplates: auto-locked cloned event %s', sender.slug)
