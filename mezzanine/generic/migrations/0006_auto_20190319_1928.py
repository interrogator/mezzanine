# Generated by Django 2.0.13 on 2019-03-19 19:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('generic', '0005_threadedcomment_chamber'),
    ]

    operations = [
        migrations.AlterField(
            model_name='threadedcomment',
            name='failed_automod',
            field=models.CharField(max_length=500),
        ),
    ]
