# Generated by Django 2.0.13 on 2019-03-19 13:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('generic', '0003_auto_20170411_0504'),
    ]

    operations = [
        migrations.AddField(
            model_name='threadedcomment',
            name='failed_automod',
            field=models.BooleanField(default=False),
        ),
    ]
