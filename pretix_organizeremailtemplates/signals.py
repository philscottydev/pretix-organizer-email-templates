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
    """
    Inject a lock-status banner at the top of the native email settings page when
    email content is locked to organizer level for this event.
    """
    request = sender

    # Only on event pages
    if not hasattr(request, 'event'):
        return ''

    # Only on the native email settings page (path ends with /settings/email)
    if not request.path_info.endswith('/settings/email'):
        return ''

    # Only when the plugin is active for this event
    if 'pretix_organizeremailtemplates' not in request.event.plugins:
        return ''

    # Only when content is locked
    is_locked = bool(request.event.settings.get('emailtemplates_content_locked', as_type=bool))
    if not is_locked:
        return ''

    # Only when organizer actually has templates set (otherwise the lock is meaningless)
    if not _organizer_has_templates(request.organizer):
        return ''

    organizer_url = reverse(
        'plugins:pretix_organizeremailtemplates:organizer.settings',
        kwargs={'organizer': request.organizer.slug},
    )
    unlock_url = reverse(
        'plugins:pretix_organizeremailtemplates:event.settings',
        kwargs={'organizer': request.organizer.slug, 'event': request.event.slug},
    ) + '?action=unlock'

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
        btn_organizer=_('Go to Organizer Email Templates'),
        unlock_url=unlock_url,
        btn_unlock=_('Unlock for This Event'),
    ))


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
    from .forms import MAIL_KEY_MAP
    source_locked = bool(other.settings.get('emailtemplates_content_locked', as_type=bool))
    if not source_locked:
        return
    # Only lock if organizer has templates
    organizer = sender.organizer
    has_templates = any(
        organizer.settings.get('emailtemplates_subject_%s' % et)
        or organizer.settings.get('emailtemplates_text_%s' % et)
        for et in MAIL_KEY_MAP
    )
    if not has_templates:
        return
    for subject_key, text_key in MAIL_KEY_MAP.values():
        sender.settings.delete(subject_key)
        sender.settings.delete(text_key)
    sender.settings.set('emailtemplates_content_locked', True)
    sender.settings.flush()
    logger.debug('organizeremailtemplates: auto-locked cloned event %s', sender.slug)
