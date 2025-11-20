from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Create test users for Locust load tests'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=100, help='Number of users to create')
        parser.add_argument('--prefix', type=str, default='locust', help='Username prefix')
        parser.add_argument('--password', type=str, default='locustpass', help='Password for all users')

    def handle(self, *args, **options):
        User = get_user_model()
        count = options['count']
        prefix = options['prefix']
        password = options['password']
        
        # Eliminar usuarios existentes con ese prefijo para asegurar que se recreen (ej. con nuevo hash)
        self.stdout.write(f'Eliminando usuarios existentes con prefijo "{prefix}"...')
        deleted, _ = User.objects.filter(username__startswith=prefix).delete()
        self.stdout.write(self.style.SUCCESS(f'Se eliminaron {deleted} usuarios anteriores.'))

        created = 0
        self.stdout.write(f'Creando {count} nuevos usuarios...')
        for i in range(1, count + 1):
            username = f"{prefix}{i}"
            User.objects.create_user(username=username, email=f"{username}@example.com", password=password)
            created += 1
        
        # Also write a credentials file that Locust can consume (username,password per line)
        try:
            out_path = 'locust_users.csv'
            with open(out_path, 'w', encoding='utf-8') as f:
                for i in range(1, count + 1):
                    username = f"{prefix}{i}"
                    f.write(f"{username},{password}\n")
            self.stdout.write(self.style.SUCCESS(f'Wrote credentials to {out_path}'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Could not write credentials file: {e}'))

        self.stdout.write(self.style.SUCCESS(f'Created {created} test users (prefix={prefix}, count={count})'))
