# Generated manually for criticidad en alertas
from django.db import migrations, models
from django.db.migrations.operations.special import SeparateDatabaseAndState


class Migration(migrations.Migration):

    dependencies = [
        ('operaciones', '0005_alerta'),
    ]

    operations = [
        SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql='''
                    ALTER TABLE "operaciones_alerta"
                    ADD COLUMN IF NOT EXISTS "criticidad" varchar(20) NULL;
                    ''',
                    reverse_sql='''
                    ALTER TABLE "operaciones_alerta"
                    DROP COLUMN IF EXISTS "criticidad";
                    ''',
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='alerta',
                    name='criticidad',
                    field=models.CharField(blank=True, max_length=20, null=True),
                ),
            ],
        ),
    ]
