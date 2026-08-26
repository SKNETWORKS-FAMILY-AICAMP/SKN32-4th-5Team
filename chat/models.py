from django.db import models


TRIAGE_MAP = {1: ('관찰', 'monitor'), 2: ('곧 방문', 'visit'),
              3: ('지금 연락', 'call'), 4: ('응급', 'emergency')}




class ChatSession(models.Model):
    session_id = models.CharField(primary_key=True, max_length=32)
    pet_id = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False              # ← Django가 이 테이블을 건드리지 않음 (읽기만)
        db_table = 'chat_sessions'   # ← 실제 테이블 이름과 연결


class ChatMessage(models.Model):
    message_id = models.CharField(primary_key=True, max_length=36)
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.DO_NOTHING,
        db_column='session_id',      # 실제 컬럼명
        related_name='messages',     # session.messages 로 접근 가능
    )
    seq = models.IntegerField()
    role = models.CharField(max_length=10)          # user / assistant
    content = models.TextField()
    response_status = models.CharField(max_length=20, null=True, blank=True)
    triage_level = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField()

    @property
    def triage_badge(self):
        return TRIAGE_MAP.get(self.triage_level, (None, None))[0]

    @property
    def triage_css(self):
        return TRIAGE_MAP.get(self.triage_level, (None, ''))[1]

    class Meta:
        managed = False
        db_table = 'chat_messages'
        ordering = ['seq']           # 대화 순서대로