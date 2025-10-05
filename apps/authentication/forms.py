# apps/authentication/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.apps import apps
from apps.authentication.models import Role
from bson import ObjectId 

User = get_user_model()


class LoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(attrs={"placeholder": "Username", "class": "form-control"})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Password", "class": "form-control"})
    )


class SignUpForm(UserCreationForm):
    # UI stays the same
    username = forms.CharField(
        widget=forms.TextInput(attrs={"placeholder": "Username", "class": "form-control"})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"placeholder": "Email", "class": "form-control"})
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Password", "class": "form-control"})
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Password check", "class": "form-control"})
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
        user.full_name = user.full_name or ""
        user.phone_number = user.phone_number or ""
        user.gender = user.gender or ""
        # date_of_birth left as None

        # ---- Contact defaults ----
        if not getattr(user, "alternate_email", None):
            user.alternate_email = None
        for field in ("address_line1", "address_line2", "city", "state", "country", "postcode"):
            setattr(user, field, getattr(user, field, "") or "")

        # ---- Preference defaults ----
        user.is_email_verified = bool(getattr(user, "is_email_verified", False))
        user.is_phone_verified = bool(getattr(user, "is_phone_verified", False))
        user.timezone = getattr(user, "timezone", None) or "UTC"
        user.language_preference = getattr(user, "language_preference", None) or "en"
        user.avatar = getattr(user, "avatar", None) or ""

        # ---- Security/auth extras ----
        # leave last_password_change/account_locked_until/mfa_secret as-is (None if unset)
        user.failed_login_attempts = int(getattr(user, "failed_login_attempts", 0))
        user.mfa_enabled = bool(getattr(user, "mfa_enabled", False))

        # ---- Audit defaults ----
        created_by = ""
        if getattr(self._request, "user", None) and self._request.user.is_authenticated:
            created_by = self._request.user.username
        user.created_by = getattr(user, "created_by", "") or created_by
        user.updated_by = getattr(user, "updated_by", "") or user.created_by

        # ---- Role default (if available) ----
        if not getattr(user, "role_id", None):
            RoleModel = apps.get_model("authentication", "Role")
            try:
                user.role = RoleModel.objects.get(name="superadmin")
            except RoleModel.DoesNotExist:
                pass

        if commit:
            user.save()
        return user


# ---------- TOP-LEVEL form for role assignment (used in role admin UI) ----------
class ObjectIdModelChoiceField(forms.ModelChoiceField):
    """Accept string ObjectIds from the browser and cast to bson.ObjectId."""
    def to_python(self, value):
        if value in (None, "", []):
            return None
        if isinstance(value, Role):
            return value
        try:
            oid = value if isinstance(value, ObjectId) else ObjectId(str(value))
        except Exception:
            raise forms.ValidationError("Invalid id format.")
        return super().to_python(oid)


User = get_user_model()

class TolerantRoleChoice(forms.ModelChoiceField):
    """
    Accept role posted as:
      - Role instance (already bound)
      - ObjectId string / ObjectId
      - legacy int id (e.g. "3")
      - role name string (e.g. "user1")
    """
    def to_python(self, value):
        # normal empties
        if value in (None, "", []):
            return None
        # already resolved
        if isinstance(value, Role):
            return value

        # Try default lookup first
        try:
            return super().to_python(value)
        except Exception:
            pass

        # Try ObjectId
        try:
            oid = value if isinstance(value, ObjectId) else ObjectId(str(value))
            return super().to_python(oid)
        except Exception:
            pass

        # Try legacy integer id
        try:
            ival = int(str(value))
            # some installs actually stored numeric _id — handle it
            return Role.objects.get(pk=ival)
        except Exception:
            pass

        # Try by name as last resort
        try:
            return Role.objects.get(name=str(value))
        except Exception:
            pass

        raise forms.ValidationError("Invalid id format.")

class AssignRoleForm(forms.ModelForm):
    role = TolerantRoleChoice(
        queryset=Role.objects.all().order_by("name"),
        empty_label=None,
        required=True,
        label="User type",
    )

    class Meta:
        model = User
        fields = ["role"]
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure all non-select fields get form-control styling (if you add more later)
        for name, field in self.fields.items():
            css = field.widget.attrs.get('class', '')
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = (css + ' form-select').strip()
            else:
                field.widget.attrs['class'] = (css + ' form-control').strip()    
