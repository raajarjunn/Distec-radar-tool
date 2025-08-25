from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()

class ProfileForm(forms.ModelForm):
    # Not model-bound: we’ll handle saving manually in the view
    avatar = forms.FileField(required=False)
    
    class Meta:
        model = User
        # Pick the fields you want to edit on the *User* table
        fields = (
            "first_name", "last_name",
            "full_name", "phone_number", "date_of_birth", "gender",
            "alternate_email",
            "address_line1", "address_line2", "city", "state", "country", "postcode",
            "timezone", "language_preference", "avatar",
        )
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
        }
