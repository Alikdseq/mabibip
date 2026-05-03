from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from . import onboarding_views
from .vkid import vkid_session_complete
from .forms import (
    EmailPasswordResetForm,
    EmailSetPasswordForm,
)

app_name = "users"

urlpatterns = [
    path(
        "complete-profile/",
        onboarding_views.complete_profile,
        name="complete_profile",
    ),
    path("email/pending/", views.email_verification_notice, name="email_verification_notice"),
    path("email/resend/", views.resend_verification_email, name="resend_verification_email"),
    path(
        "email/verify/<uidb64>/<str:token>/",
        views.verify_email,
        name="verify_email",
    ),
    path("register/sto/", views.sto_register, name="sto_register"),
    path("register/", views.register_start, name="register"),
    path("register/confirm/", views.register_confirm, name="register_confirm"),
    path(
        "activate/<uidb64>/<str:token>/",
        views.activate,
        name="activate",
    ),
    path(
        "vk/login/callback/",
        views.vk_oauth_callback_alias,
        name="vk_oauth_callback_alias",
    ),
    path("api/vkid/session/", vkid_session_complete, name="vkid_session"),
    path(
        "login/",
        views.CaptchaLoginView.as_view(),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path(
        "account/delete/",
        views.account_delete,
        name="account_delete",
    ),
    path(
        "password_reset/",
        auth_views.PasswordResetView.as_view(
            template_name="users/password_reset_form.html",
            form_class=EmailPasswordResetForm,
            email_template_name="users/email/password_reset_body.txt",
            html_email_template_name="users/email/password_reset_body.html",
            subject_template_name="users/email/password_reset_subject.txt",
            success_url=reverse_lazy("users:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password_reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="users/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="users/password_reset_confirm.html",
            form_class=EmailSetPasswordForm,
            success_url=reverse_lazy("users:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="users/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
]
