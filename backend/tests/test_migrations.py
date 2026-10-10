from alembic import command


def test_models_match_migrations(alembic_cfg):
    # Raises if the models differ from what the migrations produce, i.e. someone
    # changed a model without generating a migration.
    command.check(alembic_cfg)
