from django.db import models
from django.utils import timezone


class CompoundView(models.Model):
    
    # Primary identifier
    ns_id = models.CharField(
        max_length=100, 
        primary_key=True,
        db_column='ns_id',
        help_text='NORMAN SLE identifier'
    )
    
    # Basic compound information
    name = models.TextField(
        null=True, 
        blank=True,
        db_column='name',
        help_text='Compound name (COALESCE from multiple sources)'
    )
    
    # Chemical identifiers
    smiles = models.TextField(
        null=True, 
        blank=True,
        db_column='smiles',
        help_text='SMILES notation'
    )
    
    inchi = models.TextField(
        null=True, 
        blank=True,
        db_column='inchi',
        help_text='InChI string'
    )
    
    inchikey = models.CharField(
        max_length=27, 
        null=True, 
        blank=True,
        db_column='inchikey',
        help_text='InChIKey (27 character hash)'
    )
    
    cas = models.CharField(
        max_length=50, 
        null=True, 
        blank=True,
        db_column='cas',
        help_text='CAS Registry Number'
    )
    
    # External database identifiers
    dtxsid = models.CharField(
        max_length=100, 
        null=True, 
        blank=True,
        db_column='dtxsid',
        help_text='DSSTox Substance ID (CompTox)'
    )
    
    nsid = models.CharField(
        max_length=100, 
        null=True, 
        blank=True,
        db_column='nsid',
        help_text='NORMAN substance ID'
    )
    
    # Chemical properties
    mass = models.CharField(
        max_length=50, 
        null=True, 
        blank=True,
        db_column='mass',
        help_text='Molecular mass (as text)'
    )
    
    xlogp = models.CharField(
        max_length=50, 
        null=True, 
        blank=True,
        db_column='xlogp',
        help_text='XLogP value (as text)'
    )
    
    # Database reference IDs
    dtx_id = models.IntegerField(
        null=True, 
        blank=True,
        db_column='dtx_id',
        help_text='Internal DTX database ID'
    )
    
    pc_id = models.IntegerField(
        null=True, 
        blank=True,
        db_column='pc_id',
        help_text='Internal PubChem database ID'
    )
    
    cid = models.BigIntegerField(
        null=True, 
        blank=True,
        db_column='cid',
        help_text='PubChem Compound ID (CID)'
    )
    
    # InChIKey consistency checks
    inchikey_smiles = models.CharField(
        max_length=27, 
        null=True, 
        blank=True,
        db_column='inchikey_smiles',
        help_text='InChIKey derived from SMILES'
    )
    
    inchikey_inchi = models.CharField(
        max_length=27, 
        null=True, 
        blank=True,
        db_column='inchikey_inchi',
        help_text='InChIKey derived from InChI'
    )
    
    # Record tracking
    pc_record_id = models.IntegerField(
        null=True, 
        blank=True,
        db_column='pc_record_id',
        help_text='PubChem record ID'
    )
    
    compound_id = models.IntegerField(
        null=True, 
        blank=True,
        db_column='compound_id',
        help_text='Internal compound ID'
    )
    
    # Aggregated data
    list_count = models.BigIntegerField(
        null=True, 
        blank=True,
        db_column='list_count',
        help_text='Number of lists containing this compound'
    )
    
    # Computed numeric fields
    mass_num = models.FloatField(
        null=True, 
        blank=True,
        db_column='mass_num',
        help_text='Molecular mass as numeric (converted from text)'
    )
    
    xlogp_num = models.FloatField(
        null=True, 
        blank=True,
        db_column='xlogp_num',
        help_text='XLogP as numeric (converted from text)'
    )
    
    # Computed text processing fields
    name_lc = models.TextField(
        null=True, 
        blank=True,
        db_column='name_lc',
        help_text='Lowercase version of name for searching'
    )
    
    name_bucket = models.IntegerField(
        null=True, 
        blank=True,
        db_column='name_bucket',
        help_text='Name categorization: 0=starts with letter, 1=starts with digit, 2=other'
    )
    
    name_is_clean = models.BooleanField(
        null=True, 
        blank=True,
        db_column='name_is_clean',
        help_text='True if name contains only letters, spaces, and hyphens'
    )
    
    name_noise_len = models.IntegerField(
        null=True, 
        blank=True,
        db_column='name_noise_len',
        help_text='Count of non-letter/space/hyphen characters in name'
    )
    
    class Meta:
        managed = False  # Don't let Django manage this table
        db_table = 'mv_compound_cards'  # Your materialized view name from screenshot
        verbose_name = 'Chemical Compound'
        verbose_name_plural = 'Chemical Compounds'
        ordering = ['name']
    
    def __str__(self):
        """String representation"""
        if self.name:
            return f"{self.name} ({self.ns_id})"
        return self.ns_id
    
    def __repr__(self):
        """Developer-friendly representation"""
        return f"<CompoundView: {self.ns_id} - {self.name}>"
    



class ChatSession(models.Model):
    """Stores complete chat sessions"""
    
    session_id = models.CharField(max_length=255, unique=True, db_index=True)
    user_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    
    started_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    total_messages = models.IntegerField(default=0)
    total_cost = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'chatbot_sessions'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['session_id', 'started_at']),
            models.Index(fields=['is_active', 'last_activity']),
        ]
    
    def __str__(self):
        return f"Session {self.session_id[:8]} - {self.total_messages} msgs"


class ChatMessage(models.Model):
    """Individual user/bot messages"""
    
    MESSAGE_TYPES = [
        ('user', 'User Message'),
        ('bot', 'Bot Response'),
    ]
    
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES)
    content = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    
    # User message metadata
    is_faq_button = models.BooleanField(default=False)
    skip_tier = models.IntegerField(default=0)
    
    # Bot response metadata
    tier = models.IntegerField(null=True, blank=True)
    tier_name = models.CharField(max_length=50, null=True, blank=True)
    response_type = models.CharField(max_length=50, null=True, blank=True)
    
    similarity_score = models.FloatField(null=True, blank=True)
    result_count = models.IntegerField(null=True, blank=True)
    
    response_time_ms = models.IntegerField(null=True, blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    
    # Feedback
    helpful = models.BooleanField(null=True, blank=True)
    feedback_timestamp = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'chatbot_messages'
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['session', 'timestamp']),
            models.Index(fields=['tier', 'response_type']),
        ]
    
    def __str__(self):
        return f"{self.message_type}: {self.content[:50]}"


class RoutingLog(models.Model):
    """Logs routing decisions (first question, LLM router, follow-up, etc)"""
    
    ROUTING_TYPES = [
        ('first_question', 'First Question'),
        ('faq_button', 'FAQ Button'),
        ('llm_router', 'LLM Router'),
        ('followup', 'Follow-up'),
        ('override', 'Database Override'),
        ('negative_feedback', 'Negative Feedback'),
    ]
    
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='routing_logs')
    
    routing_type = models.CharField(max_length=30, choices=ROUTING_TYPES, db_index=True)
    timestamp = models.DateTimeField(default=timezone.now)
    
    recommended_tier = models.IntegerField(null=True, blank=True)
    is_followup = models.BooleanField(default=False)
    reasoning = models.TextField(null=True, blank=True)
    
    # Override info
    override_applied = models.BooleanField(default=False)
    override_keywords = models.JSONField(null=True, blank=True)
    
    history_length = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'chatbot_routing_logs'
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{self.routing_type} - Tier {self.recommended_tier}"


class TierAttempt(models.Model):
    """Records each tier attempt (FAQ, RAG, SQL, LLM)"""
    
    TIER_CHOICES = [
        (0, 'Follow-up'),
        (1, 'FAQ'),
        (2, 'PDF RAG'),
        (3, 'SQL Agent'),
        (4, 'LLM Fallback'),
    ]
    
    STATUS_CHOICES = [
        ('searching', 'Searching'),
        ('success', 'Success'),
        ('not_found', 'Not Found'),
        ('error', 'Error'),
    ]
    
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='tier_attempts')
    
    tier = models.IntegerField(choices=TIER_CHOICES, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    
    started_at = models.DateTimeField(default=timezone.now)
    duration_ms = models.IntegerField(null=True, blank=True)
    
    # Results
    similarity = models.FloatField(null=True, blank=True)
    result_count = models.IntegerField(null=True, blank=True)
    
    # SQL specific fields
    sql_query = models.TextField(null=True, blank=True)
    main_term = models.CharField(max_length=255, null=True, blank=True)
    synonyms = models.JSONField(null=True, blank=True)
    
    # Costs
    generation_cost = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    execution_cost = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    total_cost = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    
    class Meta:
        db_table = 'chatbot_tier_attempts'
        ordering = ['started_at']
    
    def __str__(self):
        return f"Tier {self.tier} - {self.status}"


class SystemLog(models.Model):
    """Detailed console-like logs for debugging"""
    
    LOG_TYPES = [
        ('routing', 'Routing Decision'),
        ('tier_attempt', 'Tier Attempt'),
        ('followup', 'Follow-up Detection'),
        ('override', 'Database Override'),
        ('error', 'Error'),
        ('info', 'Information'),
    ]
    
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='system_logs')
    
    log_type = models.CharField(max_length=20, choices=LOG_TYPES, db_index=True)
    timestamp = models.DateTimeField(default=timezone.now)
    
    description = models.TextField()
    details = models.JSONField(default=dict)
    
    class Meta:
        db_table = 'chatbot_system_logs'
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{self.log_type}: {self.description[:50]}"