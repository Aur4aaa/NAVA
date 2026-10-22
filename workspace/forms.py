from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from .models import Record, VersionedRecord, EvidenceVersion, AuditPack, Organization
from .permissions import visible_queryset, has_role


PROTECTED_FIELDS = {
    'id', 'status', 'revision', 'series', 'version', 'previous', 'created_by',
    'created_at', 'updated_at', 'checksum', 'original_filename', 'size_bytes',
    'content_type', 'snapshot', 'omissions', 'manifest', 'recurrence_source',
    'recurrence_key', 'verified_by', 'verified_on', 'retention_hold',
}


def record_form_class(model, user, instance=None):
    excluded = set(PROTECTED_FIELDS)
    if instance and model is EvidenceVersion:
        excluded.add('file')
    if model is AuditPack:
        excluded.add('file')
    if not has_role(user, 'Manager'):
        excluded |= {'allowed_users', 'access_expires', 'owner'}
        if instance:
            excluded.add('classification')
    fields = [f.name for f in list(model._meta.fields) + list(model._meta.many_to_many) if f.editable and f.name not in excluded]
    widgets = {}
    for field in model._meta.fields:
        if field.get_internal_type() == 'DateField':
            widgets[field.name] = forms.DateInput(attrs={'type': 'date'})
        elif field.get_internal_type() == 'DateTimeField':
            widgets[field.name] = forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M')
        elif field.get_internal_type() == 'TextField':
            widgets[field.name] = forms.Textarea(attrs={'rows': 4})

    base = forms.modelform_factory(model, fields=fields, widgets=widgets)

    class RecordForm(base):
        expected_revision = forms.IntegerField(widget=forms.HiddenInput, required=False)

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if self.instance.pk:
                self.fields['expected_revision'].initial = self.instance.revision
                self.fields['expected_revision'].required = True
            for name, field in self.fields.items():
                if hasattr(field, 'queryset') and field.queryset is not None:
                    related = field.queryset.model
                    if issubclass(related, Record):
                        field.queryset = visible_queryset(user, field.queryset)
                    elif related is get_user_model():
                        field.queryset = related.objects.filter(is_active=True).order_by('first_name', 'username')
                field.widget.attrs.setdefault('class', 'form-control')
                if name in ('allowed_users', 'controls', 'risks', 'requirements', 'evidence', 'documents', 'dependencies', 'assets', 'actions') and hasattr(field, 'queryset'):
                    field.widget.attrs['size'] = 5
                    field.help_text = 'Select one or more records. Hold Ctrl (Windows) or Command (Mac) to select multiple.'
            if 'file' in self.fields:
                self.fields['file'].help_text = 'Up to 10 MB. PDF, plain text, CSV, PNG, JPEG, DOCX, XLSX. Files are private. Malware scanning is not available.'
            if 'classification' in self.fields:
                self.fields['classification'].help_text = 'Restricted records require explicit access. Managers can also see confidential records. Share related evidence separately.'
            if 'access_expires' in self.fields:
                self.fields['access_expires'].help_text = 'Required for any explicitly shared external auditor access. Use the organization timezone.'
            if 'effectiveness' in self.fields:
                self.fields['effectiveness'].help_text = 'Record a human evaluation with dated test results and evidence. Uploading a file does not establish effectiveness.'

        def clean(self):
            data = super().clean()
            if model is EvidenceVersion and not self.instance.pk and not data.get('file') and not data.get('external_url'):
                raise forms.ValidationError('Upload a file or provide an external reference URL.')
            if data.get('period_start') and data.get('period_end') and data['period_end'] < data['period_start']:
                self.add_error('period_end', 'The coverage end must not be earlier than the start.')
            if 'dependencies' in data and self.instance.pk and self.instance in data['dependencies']:
                self.add_error('dependencies', 'A task cannot depend on itself.')
            if data.get('effectiveness') == 'effective' and (not data.get('effectiveness_notes') or not data.get('tested_on') or not data.get('evidence')):
                self.add_error('effectiveness', 'Record the test date, evaluation notes, and supporting evidence before marking effectiveness verified.')
            if data.get('effectiveness_verified') and not data.get('evidence'):
                self.add_error('effectiveness_verified', 'Link evidence supporting the effectiveness assessment.')
            return data

    return RecordForm


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ['name', 'description', 'timezone']

    def clean_timezone(self):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        value = self.cleaned_data['timezone']
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise forms.ValidationError('Enter an IANA timezone, such as Asia/Kuala_Lumpur.')
        return value


class AccountForm(forms.Form):
    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    password = forms.CharField(widget=forms.PasswordInput, min_length=12)
    roles = forms.ModelMultipleChoiceField(queryset=Group.objects.all(), required=True, widget=forms.CheckboxSelectMultiple)

    def clean_username(self):
        value = self.cleaned_data['username']
        if get_user_model().objects.filter(username=value).exists():
            raise forms.ValidationError('This username already exists.')
        return value

    def clean_password(self):
        from django.contrib.auth.password_validation import validate_password
        value = self.cleaned_data['password']
        validate_password(value)
        return value


class ShareForm(forms.Form):
    users = forms.ModelMultipleChoiceField(queryset=get_user_model().objects.filter(is_active=True), required=False, label='Explicitly allowed users')
    expires_at = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}), label='External access expiry')
    reason = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={'rows': 2}))
    revision = forms.IntegerField(widget=forms.HiddenInput)
