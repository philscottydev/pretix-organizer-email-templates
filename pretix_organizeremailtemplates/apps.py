import logging

from django.utils.translation import gettext_lazy as _
from pretix.base.plugins import PluginConfig, PLUGIN_LEVEL_EVENT_ORGANIZER_HYBRID

logger = logging.getLogger(__name__)


class PluginApp(PluginConfig):
    name = 'pretix_organizeremailtemplates'
    label = 'pretix_organizeremailtemplates'
    verbose_name = _('Organizer Email Templates')

    class PretixPluginMeta:
        name = _('Organizer Email Templates')
        author = 'Phil Scott'
        description = _('Organizer-level email content template management with per-event lock/unlock')
        version = '1.5.0'
        category = 'CUSTOMIZATION'
        level = PLUGIN_LEVEL_EVENT_ORGANIZER_HYBRID
        compatibility = "pretix>=2026.2.0"
        visible = True

    def ready(self):
        from . import signals  # NOQA

    def installed(self, event):
        """
        Called by pretix when the plugin is first enabled on an event.
        If the organizer has opted in to auto-lock new events and has templates
        configured, delete any event-level mail_* keys and set the lock flag.
        """
        auto_lock = event.organizer.settings.get(
            'emailtemplates_auto_lock_new_events', as_type=bool
        )
        if not auto_lock:
            return

        from .forms import apply_organizer_templates_to_event, EMAIL_TYPES
        # Check organizer actually has at least one template configured
        organizer = event.organizer
        has_templates = any(
            organizer.settings.get('emailtemplates_subject_%s' % et)
            or organizer.settings.get('emailtemplates_text_%s' % et)
            for et, _label in EMAIL_TYPES
        )
        if not has_templates:
            return
        apply_organizer_templates_to_event(event.organizer, event)
        event.settings.set('emailtemplates_content_locked', True)
        # flush is called inside apply_organizer_templates_to_event
        logger.debug(
            'organizeremailtemplates: auto-locked event %s on plugin install', event.slug
        )


default_app_config = 'pretix_organizeremailtemplates.apps.PluginApp'
