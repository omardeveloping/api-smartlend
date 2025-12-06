# Generated manually for banning logic and director de carrera notifications
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0006_alter_usuario_embedding'),
    ]

    operations = [
        migrations.CreateModel(
            name='DirectorCarrera',
            fields=[
                ('id_director', models.AutoField(primary_key=True, serialize=False)),
                ('nombre', models.CharField(max_length=100)),
                ('correo', models.EmailField(max_length=100)),
                ('carrera', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='director', to='usuarios.carrera')),
            ],
        ),
        migrations.AddField(
            model_name='usuario',
            name='ban_notified',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='usuario',
            name='banned_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='usuario',
            name='is_banned',
            field=models.BooleanField(default=False),
        ),
    ]
