from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.apps import apps
from datetime import datetime
from django.utils import timezone

User = get_user_model()


class LoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "placeholder": "Username",
                "class": "form-control"
            }
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Password",
                "class": "form-control"
            }
        )
    )


class SignUpForm(UserCreationForm):
    # UI stays the same
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "placeholder": "Username",
                "class": "form-control"
                }
            )
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "placeholder": "Email",
                "class": "form-control"
                }
            )
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Password",
                "class": "form-control"
                }
            )
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Password check",
                "class": "form-control"
                }
            )
    )

    # allow passing request from the view so we can set created_by
    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._request = request

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with that email already exists.")
        return email

    def save(self, commit=True):
        """
        Create the user and silently set defaults for extended fields.
        The UI remains unchanged.
        """
        user = super().save(commit=False)

        # ---- Profile defaults ----
        if not getattr(user, "full_name", None):
            user.full_name = ""
        if not getattr(user, "phone_number", None):
            user.phone_number = ""
        # date_of_birth left as None unless you want a sentinel date
        if not getattr(user, "gender", None):
            user.gender = ""  # or use a controlled value like "Other"

        # ---- Contact defaults ----
        if not getattr(user, "alternate_email", None):
            user.alternate_email = None
        for field in ("address_line1", "address_line2", "city", "state", "country", "postcode"):
            if not getattr(user, field, None):
                setattr(user, field, "")

        # ---- Preference defaults ----
        if not getattr(user, "is_email_verified", None):
            user.is_email_verified = False
        if not getattr(user, "is_phone_verified", None):
            user.is_phone_verified = False
        if not getattr(user, "timezone", None):
            user.timezone = "UTC"
        if not getattr(user, "language_preference", None):
            user.language_preference = "en"
        if not getattr(user, "avatar", None):
            user.avatar = ""

        # ---- Security/auth extras ----
        if not getattr(user, "last_password_change", None):
            user.last_password_change = None
        if not getattr(user, "failed_login_attempts", None):
            user.failed_login_attempts = 0
        if not getattr(user, "account_locked_until", None):
            user.account_locked_until = None
        if not getattr(user, "mfa_enabled", None):
            user.mfa_enabled = False
        if not getattr(user, "mfa_secret", None):
            user.mfa_secret = None

        # ---- Audit defaults ----
        # created_at/updated_at are auto-managed by the model
        if not getattr(user, "created_by", None):
            user.created_by = (self._request.user.username if getattr(self._request, "user", None) and self._request.user.is_authenticated else "")
        if not getattr(user, "updated_by", None):
            user.updated_by = user.created_by

        # ---- Role default (if available) ----
        if not getattr(user, "role_id", None):
            Role = apps.get_model("authentication", "Role")
            try:
                user.role = Role.objects.get(name="user1")
            except Role.DoesNotExist:
                pass

        if commit:
            user.save()
            # For Djongo safety: if pk is not visible on the instance yet, re-fetch
            if getattr(user, "pk", None) is None:
                persisted = User.objects.filter(username=user.username).first()
                if persisted:
                    user = persisted

        return user