# chatbot/models.py

from django.db import models

class CompoundView(models.Model):
    """
    Django model for the mv_compound_cards materialized view
    Read-only model representing chemical compounds data
    """
    
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