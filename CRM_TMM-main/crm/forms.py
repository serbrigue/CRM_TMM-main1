from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django import forms 
from .models import Cliente
from .models import Taller


class TallerForm(forms.ModelForm):
    """Form para crear/editar un Taller desde la interfaz de administración interna."""
    class Meta:
        model = Taller
        fields = ['nombre', 'descripcion', 'categoria', 'fecha_taller', 'hora_taller', 'modalidad', 'precio', 'cupos_totales', 'esta_activo', 'imagen']
        widgets = {
            'fecha_taller': forms.DateInput(attrs={'type': 'date'}),
            'hora_taller': forms.TimeInput(attrs={'type': 'time'}),
        }


class AdminEmailForm(forms.Form):
    """Formulario mínimo para enviar correos desde la UI de gestión de talleres."""
    asunto = forms.CharField(max_length=255, required=True, label='Asunto')
    mensaje = forms.CharField(widget=forms.Textarea, required=True, label='Mensaje')
    plantilla = forms.ChoiceField(required=False, choices=[('personalizado','Personalizado'), ('recordatorio','Recordatorio'), ('info_taller', 'Información Taller'), ('cancelacion','Cancelación')], label='Plantilla (opcional)')

class RegistroClienteForm(UserCreationForm):
    """
    Formulario personalizado para el registro de nuevos clientes.
    Añade campos para teléfono y fecha de nacimiento.
    """
    # 1. Añadir campos adicionales para el modelo Cliente
    telefono = forms.CharField(max_length=20, required=False, label="Teléfono (Ej: +569...)")
    fecha_nacimiento = forms.DateField(
        required=False, 
        label="Fecha de Nacimiento (DD/MM/AAAA)", 
        widget=forms.DateInput(attrs={'type': 'date'}) # Widget de fecha HTML5
    )
    
    class Meta:
        model = User
        # Mantenemos los campos esenciales de User
        fields = ("username", "email", "first_name", "last_name")
    
    # 2. Modificar el método save para guardar los datos en el modelo Cliente
    def save(self, commit=True):
        user = super().save(commit=commit)
        
        # Obtener los datos adicionales del formulario
        telefono_data = self.cleaned_data.get('telefono')
        nacimiento_data = self.cleaned_data.get('fecha_nacimiento')
        
        # Actualizar o crear el objeto Cliente CRM
        Cliente.objects.update_or_create(
            email=user.email,
            defaults={
                'nombre_completo': f"{user.first_name} {user.last_name}".strip(),
                'telefono': telefono_data,
                'fecha_nacimiento': nacimiento_data,
            }
        )
        return user
    
    def clean_email(self):
        # Aseguramos que el email no esté ya registrado
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Este correo electrónico ya está registrado.")
        return email