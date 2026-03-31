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


.. _pretix: https://github.com/pretix/pretix
.. _pretix development setup: https://docs.pretix.eu/en/latest/development/setup.html
