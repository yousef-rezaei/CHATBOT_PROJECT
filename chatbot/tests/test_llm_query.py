from django.test import TestCase
from chatbot.llm_query_generator import LLMQueryGenerator
from chatbot.query_validator import QueryValidator
from chatbot.query_executor import QueryExecutor

class LLMQueryTests(TestCase):
    
    def setUp(self):
        self.generator = LLMQueryGenerator()
        self.validator = QueryValidator(allowed_tables=['chemical_data_view'])
    
    def test_generate_simple_query(self):
        """Test generating a simple SELECT query"""
        question = "Find chemicals with benzene in the name"
        result = self.generator.generate_query(question)
        
        self.assertIsNotNone(result)
        self.assertIn('SELECT', result['query'].upper())
        self.assertIn('benzene', result['query'].lower())
    
    def test_validate_safe_query(self):
        """Test validating a safe SELECT query"""
        query = "SELECT * FROM chemical_data_view WHERE chemical_name LIKE '%benzene%' LIMIT 10"
        result = self.validator.validate(query)
        
        self.assertTrue(result['valid'])
        self.assertIsNone(result['error'])
    
    def test_reject_insert_query(self):
        """Test rejecting INSERT query"""
        query = "INSERT INTO chemical_data_view (chemical_name) VALUES ('test')"
        result = self.validator.validate(query)
        
        self.assertFalse(result['valid'])
        self.assertIn('INSERT', result['error'])
    
    def test_reject_delete_query(self):
        """Test rejecting DELETE query"""
        query = "DELETE FROM chemical_data_view WHERE id = 1"
        result = self.validator.validate(query)
        
        self.assertFalse(result['valid'])
        self.assertIn('DELETE', result['error'])
    
    def test_reject_drop_query(self):
        """Test rejecting DROP query"""
        query = "DROP TABLE chemical_data_view"
        result = self.validator.validate(query)
        
        self.assertFalse(result['valid'])
        self.assertIn('DROP', result['error'])
    
    def test_reject_sql_injection(self):
        """Test rejecting SQL injection attempt"""
        query = "SELECT * FROM chemical_data_view; DROP TABLE users; --"
        result = self.validator.validate(query)
        
        self.assertFalse(result['valid'])