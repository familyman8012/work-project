# Generated by Django 5.0.3 on 2024-10-31 07:49

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Department',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='부서명')),
                ('code', models.CharField(max_length=10, unique=True, verbose_name='부서코드')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='children', to='organizations.department', verbose_name='상위부서')),
            ],
            options={
                'verbose_name': '부서',
                'verbose_name_plural': '부서들',
            },
        ),
    ]
