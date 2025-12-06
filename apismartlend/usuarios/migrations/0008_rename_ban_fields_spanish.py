# Generated manually to renombrar campos de baneo a español, tolerando esquemas ya renombrados
from django.db import migrations, models


def rename_column_if_exists(table, old, new):
    return migrations.RunSQL(
        sql=f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = '{table}'
                  AND column_name = '{old}'
            ) THEN
                EXECUTE 'ALTER TABLE "{table}" RENAME COLUMN "{old}" TO "{new}"';
            END IF;
        END$$;
        """,
        reverse_sql=f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = '{table}'
                  AND column_name = '{new}'
            ) THEN
                EXECUTE 'ALTER TABLE "{table}" RENAME COLUMN "{new}" TO "{old}"';
            END IF;
        END$$;
        """,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0007_directorcarrera_usuario_is_banned'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                rename_column_if_exists('usuarios_usuario', 'is_banned', 'esta_baneado'),
                rename_column_if_exists('usuarios_usuario', 'banned_at', 'baneado_en'),
                rename_column_if_exists('usuarios_usuario', 'ban_notified', 'aviso_ban_enviado'),
            ],
            state_operations=[
                migrations.RenameField(
                    model_name='usuario',
                    old_name='is_banned',
                    new_name='esta_baneado',
                ),
                migrations.RenameField(
                    model_name='usuario',
                    old_name='banned_at',
                    new_name='baneado_en',
                ),
                migrations.RenameField(
                    model_name='usuario',
                    old_name='ban_notified',
                    new_name='aviso_ban_enviado',
                ),
            ],
        ),
    ]
