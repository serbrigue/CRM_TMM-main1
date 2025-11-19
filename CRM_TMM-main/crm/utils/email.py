from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from ..models import EmailLog


def send_email(recipient, subject, text_body, html_body=None, inscripcion=None, sender_name=None):
    """Send an email and log the attempt to EmailLog.

    Returns a tuple (ok: bool, error_message: str|None)
    """
    try:
        # Format from_email to include sender name when provided
        if sender_name:
            from_email = f"{sender_name} <{settings.DEFAULT_FROM_EMAIL}>"
        else:
            from_email = settings.DEFAULT_FROM_EMAIL

        if html_body:
            msg = EmailMultiAlternatives(subject=subject, body=text_body, from_email=from_email, to=[recipient])
            msg.attach_alternative(html_body, "text/html")
            msg.send(fail_silently=False)
        else:
            msg = EmailMultiAlternatives(subject=subject, body=text_body, from_email=from_email, to=[recipient])
            msg.send(fail_silently=False)

        # Log success
        EmailLog.objects.create(
            recipient=recipient,
            subject=subject,
            body_text=text_body,
            body_html=html_body,
            status='SUCCESS',
            inscripcion=inscripcion
        )
        return True, None
    except Exception as e:
        err = str(e)
        try:
            EmailLog.objects.create(
                recipient=recipient,
                subject=subject,
                body_text=text_body,
                body_html=html_body,
                status='FAIL',
                error_message=err,
                inscripcion=inscripcion
            )
        except Exception:
            # If logging fails, ignore to not mask original error
            pass
        return False, err
