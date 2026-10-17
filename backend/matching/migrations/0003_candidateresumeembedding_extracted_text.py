# Generated manually for Phase 4: Secure Resume Text Extraction Foundation

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('matching', '0002_candidateresumeembedding_jobembedding'),
    ]

    operations = [
        migrations.AddField(
            model_name='candidateresumeembedding',
            name='extracted_text',
            field=models.TextField(
                blank=True,
                null=True,
                help_text='Normalized plain text extracted from candidate resume file. Strictly private.',
            ),
        ),
    ]
