Organizer Email Templates for pretix
=====================================

This is a plugin for `pretix`_ that lets organizers define default email
templates for all 13 standard email types. Events can inherit these templates
or override them with event-specific content using a lock/unlock mechanism.


Features
--------

* Set organization-wide default subjects and bodies for all 13 pretix email
  types (placed order, paid order, free order, resend link, order changed,
  payment reminder, payment failed, waiting list, order canceled, custom mail,
  download reminder, order approved, order denied)
* Multi-language support — one input per active locale
* Pre-fills the organizer form with pretix's built-in defaults on first use
* Events can be **locked** to inherit organizer templates, or **unlocked** to
  use event-specific content
* Lock/unlock controls on both the plugin's event page and pretix's native
  email settings page (banner injected when locked)
* Edit/Preview tabs and clickable placeholder insertion buttons (same UI as
  pretix's native email settings)
* AJAX preview for organizer-level templates
* **Auto-lock on activation** — when an organizer enables the plugin on a new
  event, the event is automatically locked to organizer templates if the
  *Auto-lock new events* setting is enabled and organizer templates exist
* **Auto-lock propagation on clone** — when a locked event is cloned, the new
  event inherits the locked state automatically
* **"Auto-lock new events" setting** — per-organizer checkbox on the
  organizer templates form to control the auto-lock-on-activation behaviour


How it works
------------

**Organizer level**

Go to *Organizer settings → Event email templates*. Enter subjects and body
text for each email type. Values are stored under
``emailtemplates_subject_<type>`` / ``emailtemplates_text_<type>`` in
organizer settings.

**Event level**

Go to *Event settings → Email content*. By default the event is unlocked and
uses pretix's own per-event mail settings. After saving organizer templates,
you can click *Lock to organizer templates* — pretix will then read the
organizer values for all mail sends (via hierarkey cascade). Clicking
*Unlock* copies the organizer values into event settings so you can customize
from there.

**Lock state indicator**

When an event is locked, a banner is injected at the top of pretix's native
*Settings → Email* page explaining that content is managed at organizer level,
with buttons to view the organizer templates or unlock the event.


Compatibility
-------------

This plugin requires pretix 2026.2.0 or later and Python 3.11 or later.
No database migrations are required — all state is stored in pretix's
existing hierarkey settings infrastructure.


Installation
------------

Install from PyPI::

    pip install pretix-organizer-email-templates

In your pretix config, add the plugin to the installed plugins or enable it
per-organizer in the admin under *Organizer settings → Plugins*.

After enabling, two new menu items appear:

* *Organizer settings → Event email templates* — configure organization-wide
  defaults
* *Event settings → Email content* — manage per-event content and lock state


Development setup
-----------------

1. Make sure that you have a working `pretix development setup`_.

2. Clone this repository::

       git clone https://github.com/philscottydev/pretix-organizer-email-templates.git

3. Activate the virtual environment you use for pretix development.

4. Execute ``pip install -e .`` within this directory to register this
   application with pretix's plugin registry.

5. Restart your local pretix server. You can now use the plugin from this
   repository for your events by enabling it in the *Plugins* tab in the
   organizer settings.


Contributing
------------

If you like to contribute to this project, you are very welcome to do so.
If you have any questions in the process, please do not hesitate to ask.

Please report bugs and feature requests at
https://github.com/philscottydev/pretix-organizer-email-templates/issues.


License
-------

Copyright 2026 Phil Scott

Released under the terms of the Apache License 2.0.


Changelog
---------

v1.5.0 (2026-04-01)
~~~~~~~~~~~~~~~~~~~~

* **Bug fix:** Organizer template changes now immediately propagate to all
  locked events. Previously, ``form_valid()`` was overridden but
  ``OrganizerSettingsFormView.post()`` bypasses ``form_valid()`` entirely,
  so propagation never ran. Fixed by overriding ``post()`` instead.

v1.4.0 (2026-04-01)
~~~~~~~~~~~~~~~~~~~~

* **Bug fix (critical):** Locked events now correctly receive organizer email
  templates in outgoing emails. Previously, locking deleted event ``mail_*``
  keys expecting hierarkey cascade from the organizer — but the organizer only
  stores templates under ``emailtemplates_*`` keys, so pretix fell back to
  built-in defaults. Lock now copies organizer templates directly into the
  event's ``mail_*`` keys.
* Organizer template saves now automatically propagate updated templates to
  all currently-locked events.
* All lock entry points fixed: lock POST, lock GET, ``installed()`` hook,
  and ``event_copy_data`` signal.

v1.3.0 (2026-04-01)
~~~~~~~~~~~~~~~~~~~~

* **Reverse banner on native email settings page** — when email content is
  *not* locked and the organizer has templates configured, a yellow
  ``alert-warning`` banner now appears on pretix's native
  *Settings → Email* page. The banner ("Email content is managed per-event")
  explains that organizer-level templates are available and offers two buttons:
  *Lock to Organizer Templates* (locks immediately via ``GET ?action=lock``)
  and *View Organizer Templates* (opens organizer settings in a new tab).
* **GET ``?action=lock`` support in ``EventEmailContentView``** — mirrors the
  existing ``GET ?action=unlock`` shortcut so the banner button can trigger a
  lock without a full form POST.

v1.2.0 (2026-04-01)
~~~~~~~~~~~~~~~~~~~~

* **Auto-lock on plugin activation** — ``PluginApp.installed()`` now reads the
  new ``emailtemplates_auto_lock_new_events`` organizer setting and, when
  enabled and organizer templates exist, automatically locks the event to use
  organizer templates the moment the plugin is enabled on it.
* **Auto-lock propagation on event clone** — new ``on_event_copy_data``
  receiver on the ``event_copy_data`` signal: if the source event was locked,
  the cloned event is locked to organizer templates as well.
* **"Auto-lock new events" checkbox** — new ``emailtemplates_auto_lock_new_events``
  boolean field in ``OrganizerEmailTemplatesForm``, stored in
  ``organizer.settings``, gives organizers per-organizer control over the
  auto-lock behaviour.

v1.1.0 (2026-03-31)
~~~~~~~~~~~~~~~~~~~~

* Initial public release.
* Organizer-level email template management for all 13 pretix email types.
* Per-event lock/unlock mechanism using hierarkey cascade.
* Lock status banner injected on pretix's native email settings page.
* Multi-language support and pre-fill from pretix built-in defaults.
* Edit/Preview tabs, placeholder insertion buttons, and AJAX preview.


.. _pretix: https://github.com/pretix/pretix
.. _pretix development setup: https://docs.pretix.eu/en/latest/development/setup.html
