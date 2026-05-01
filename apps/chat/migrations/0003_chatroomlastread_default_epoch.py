from django.db import migrations, models

import apps.chat.models


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0002_chatroomlastread"),
    ]

    operations = [
        migrations.AlterField(
            model_name="chatroomlastread",
            name="last_read_at",
            field=models.DateTimeField(default=apps.chat.models.ChatRoomLastRead.epoch),
        ),
    ]

