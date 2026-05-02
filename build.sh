#!/usr/bin/env bash
# build.sh - Script de build para Render
set -o errexit

echo "📦 Instalando dependencias..."
pip install -r requirements.txt

echo "📁 Recolectando archivos estáticos..."
python manage.py collectstatic --no-input

echo "🗄️ Aplicando migraciones..."
python manage.py migrate

echo "✅ Build completado."



# Crear superusuario automáticamente si no existe
echo "👤 Verificando superusuario..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@fiberlux.pe', 'Admin2025!')
    print('Superusuario creado: admin / Admin2025!')
else:
    print('Superusuario ya existe.')
"