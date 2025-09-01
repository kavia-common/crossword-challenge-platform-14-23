from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='crosswordentry',
            name='direction',
            field=models.CharField(choices=[('across', 'Across'), ('down', 'Down')], max_length=6),
        ),
    ]
