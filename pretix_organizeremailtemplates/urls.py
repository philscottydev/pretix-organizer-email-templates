from django.urls import re_path

from . import views

urlpatterns = [
    re_path(
        r'^control/organizer/(?P<organizer>[^/]+)/email-templates/$',
        views.OrganizerEmailTemplatesView.as_view(),
        name='organizer.settings',
    ),
    re_path(
        r'^control/organizer/(?P<organizer>[^/]+)/email-templates/preview$',
        views.OrganizerEmailTemplatesPreview.as_view(),
        name='organizer.settings.preview',
    ),
    re_path(
        r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/email-content/$',
        views.EventEmailContentView.as_view(),
        name='event.settings',
    ),
]
