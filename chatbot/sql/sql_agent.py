"""
SQL Agent - Generates and executes SQL queries on mv_compound_cards
Cost-optimized with smart prompting
"""

import os
import time
import json
from django.db import connection


class SQLAgent:
    """
    Converts natural language questions to SQL queries
    Executes on mv_compound_cards materialized view
    """
    
    def __init__(self):
        """Initialize SQL Agent"""
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.view_name = "mv_compound_cards"  # ← CORRECT TABLE NAME
        
        # Cost tracking
        self.total_cost = 0.0
        
        if self.api_key:
            print("✅ SQL Agent initialized with LLM")
        else:
            print("⚠️ No OpenAI API key - SQL Agent disabled")
    
    def answer(self, user_question: str):
        """
        Answer question using SQL query generation
        
        Args:
            user_question: User's natural language question
            
        Returns:
            dict with 'found', 'answer', 'sql_query', 'timing', 'cost'
        """
        start_time = time.time()
        
        print(f"\n{'='*60}")
        print(f"🤖 SQL Agent Query: {user_question}")
        print(f"{'='*60}")
        
        if not self.api_key:
            return self._no_llm_response()
        
        # Step 1: Generate SQL query
        gen_start = time.time()
        sql_query = self._generate_sql_query(user_question)
        gen_time = time.time() - gen_start
        gen_cost = 0.00015  # Approximate for query generation
        
        if not sql_query:
            print("❌ Failed to generate SQL query")
            return self._default_llm_response(user_question, gen_cost, gen_time)
        
        print(f"✅ Generated SQL query:")
        print(f"   {sql_query}")
        
        # Step 2: Execute query
        exec_start = time.time()
        results, error = self._execute_query(sql_query)
        exec_time = time.time() - exec_start
        
        if error:
            print(f"❌ Query execution failed: {error}")
            return self._default_llm_response(user_question, gen_cost, gen_time)
        
        if not results:
            print("⚠️ Query returned no results")
            return self._no_results_response(sql_query, gen_cost, gen_time, exec_time)
        
        print(f"✅ Query returned {len(results)} results")
        
        # Step 3: Format results with LLM
        format_start = time.time()
        answer = self._format_results_with_llm(user_question, results, sql_query)
        format_time = time.time() - format_start
        format_cost = 0.0001  # Approximate for formatting
        
        total_time = time.time() - start_time
        total_cost = gen_cost + format_cost
        
        print(f"✅ Answer generated")
        print(f"⏱️  Timing: gen={gen_time*1000:.0f}ms, exec={exec_time*1000:.0f}ms, format={format_time*1000:.0f}ms")
        print(f"💰 Cost: ${total_cost:.6f}")
        print(f"{'='*60}\n")
        
        return {
            'found': True,
            'answer': answer,
            'sql_query': sql_query,
            'result_count': len(results),
            'timing': {
                'generation_ms': gen_time * 1000,
                'execution_ms': exec_time * 1000,
                'formatting_ms': format_time * 1000,
                'total_ms': total_time * 1000
            },
            'cost': {
                'generation': gen_cost,
                'formatting': format_cost,
                'total': total_cost
            }
        }
    
    def _generate_sql_query(self, question: str) -> str:
        """
        Generate SQL query from natural language
        Cost-optimized prompt
        """
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=self.api_key)
            
            # Cost-optimized schema description (only essential fields)
            # IMPORTANT: Table name is mv_compound_cards
            schema = """
mv_compound_cards materialized view has these ESSENTIAL columns:

**IMPORTANT: Table name is: mv_compound_cards**

**Identifiers:**
- ns_id (text): NORMAN Suspect ID (primary key)
- cas (text): CAS Registry Number
- inchikey (text): InChIKey
- dtxsid (text): DSSTox Substance ID

**Names:**
- name (text): Compound name
- name_lc (text): Lowercase name for searching

**Properties:**
- mass_num (numeric): Molecular mass
- xlogp_num (numeric): Log P value
- smiles (text): SMILES notation

**Stats:**
- list_count (integer): Number of suspect lists containing this compound

**Computed:**
- name_bucket (integer): 0=starts with letter, 1=number, 2=other
- name_is_clean (boolean): Name has only letters/spaces/hyphens
"""
            
            # Cost-optimized prompt (concise, clear instructions)
            prompt = f"""{schema}

User question: "{question}"

Generate a PostgreSQL SELECT query on mv_compound_cards.

CRITICAL RULES:
1. Table name is: mv_compound_cards
2. Use ONLY columns listed above
3. Use ILIKE for text search (case-insensitive)
4. LIMIT 10 for safety
5. Return ONLY the SQL query, no explanation

Examples:
Q: "Find compounds with benzene"
A: SELECT name, cas, mass_num FROM mv_compound_cards WHERE name_lc ILIKE '%benzene%' LIMIT 10;

Q: "Compounds in more than 50 lists"
A: SELECT name, cas, list_count FROM mv_compound_cards WHERE list_count > 50 ORDER BY list_count DESC LIMIT 10;

Q: "What is the mass of caffeine?"
A: SELECT name, mass_num, cas FROM mv_compound_cards WHERE name_lc ILIKE '%caffeine%' LIMIT 10;

Now generate SQL for: "{question}"

SQL:"""
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a PostgreSQL expert. Generate only valid SQL queries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,  # Deterministic
                max_tokens=150  # Short query only
            )
            
            sql = response.choices[0].message.content.strip()
            
            # Clean up response
            sql = sql.replace('```sql', '').replace('```', '').strip()
            
            # FORCE correct table name
            sql = sql.replace('CompoundView', 'mv_compound_cards')
            sql = sql.replace('compoundview', 'mv_compound_cards')
            sql = sql.replace('COMPOUNDVIEW', 'mv_compound_cards')
            
            # Validate basic SQL structure
            if not sql.upper().startswith('SELECT'):
                return None
            
            if 'mv_compound_cards' not in sql:
                return None
            
            return sql
            
        except Exception as e:
            print(f"⚠️ SQL generation error: {e}")
            return None
    
    def _execute_query(self, sql_query: str):
        """
        Execute SQL query safely
        Returns (results, error)
        """
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql_query)
                
                # Get column names
                columns = [col[0] for col in cursor.description]
                
                # Fetch results
                rows = cursor.fetchall()
                
                # Convert to list of dicts
                results = []
                for row in rows:
                    results.append(dict(zip(columns, row)))
                
                return results, None
                
        except Exception as e:
            return None, str(e)
    
    def _format_results_with_llm(self, question: str, results: list, sql_query: str) -> str:
        """
        Format query results into natural language answer
        Cost-optimized
        """
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=self.api_key)
            
            # Limit results to save tokens
            limited_results = results[:5]
            
            # Format results concisely
            results_text = json.dumps(limited_results, indent=2, default=str)[:1000]
            
            prompt = f"""Question: "{question}"

SQL Query: {sql_query}

Results ({len(results)} total, showing first {len(limited_results)}):
{results_text}

Provide a concise, natural language answer. Include:
- Direct answer to the question
- Key data points (names, CAS numbers, masses if relevant)
- Total count if multiple results

Keep it under 150 words."""
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful chemical database assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200  # Concise answer
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"⚠️ Formatting error: {e}")
            # Fallback to simple formatting
            return self._format_results_simple(results)
    
    def _format_results_simple(self, results: list) -> str:
        """Simple text formatting fallback"""
        if not results:
            return "No results found."
        
        answer = f"Found {len(results)} compound(s):\n\n"
        
        for i, r in enumerate(results[:5], 1):
            name = r.get('name', 'N/A')
            cas = r.get('cas', 'N/A')
            mass = r.get('mass_num', 'N/A')
            
            answer += f"{i}. **{name}**\n"
            if cas != 'N/A':
                answer += f"   CAS: {cas}\n"
            if mass != 'N/A':
                answer += f"   Mass: {mass} Da\n"
        
        if len(results) > 5:
            answer += f"\n_...and {len(results) - 5} more_"
        
        return answer
    
    def _no_results_response(self, sql_query, gen_cost, gen_time, exec_time):
        """Response when query returns no results"""
        return {
            'found': False,
            'answer': "I generated a database query, but it returned no results. Try rephrasing your question or being more specific.",
            'sql_query': sql_query,
            'result_count': 0,
            'timing': {
                'generation_ms': gen_time * 1000,
                'execution_ms': exec_time * 1000,
                'formatting_ms': 0,
                'total_ms': (gen_time + exec_time) * 1000
            },
            'cost': {
                'generation': gen_cost,
                'formatting': 0,
                'total': gen_cost
            }
        }
    
    def _default_llm_response(self, question, gen_cost, gen_time):
        """
        Default LLM response when SQL generation fails
        Direct answer without database
        """
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=self.api_key)
            
            prompt = f"""The user asked: "{question}"

This is about the NORMAN chemical database, but I couldn't generate a database query.

Provide a brief, helpful response:
- If it's a general question about chemicals, provide basic chemical knowledge
- If it's about the database, explain you need more specific details
- Keep it under 100 words"""
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful chemistry assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=150
            )
            
            answer = response.choices[0].message.content.strip()
            default_cost = 0.0001
            
            return {
                'found': True,
                'answer': answer,
                'sql_query': None,
                'result_count': 0,
                'timing': {
                    'generation_ms': gen_time * 1000,
                    'execution_ms': 0,
                    'formatting_ms': 0,
                    'total_ms': gen_time * 1000
                },
                'cost': {
                    'generation': gen_cost,
                    'formatting': default_cost,
                    'total': gen_cost + default_cost
                }
            }
            
        except Exception as e:
            print(f"⚠️ Default response error: {e}")
            return self._no_llm_response()
    
    def _no_llm_response(self):
        """Response when no LLM available"""
        return {
            'found': False,
            'answer': "I need an OpenAI API key to answer database questions. Please check the FAQ or documentation instead.",
            'sql_query': None,
            'result_count': 0,
            'timing': {'generation_ms': 0, 'execution_ms': 0, 'formatting_ms': 0, 'total_ms': 0},
            'cost': {'generation': 0, 'formatting': 0, 'total': 0}
        }


# Global instance
_sql_agent = None


def get_sql_agent():
    """Get or create SQL Agent instance"""
    global _sql_agent
    if _sql_agent is None:
        _sql_agent = SQLAgent()
    return _sql_agent