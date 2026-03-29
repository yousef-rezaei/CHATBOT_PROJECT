import os
import time
import json
from django.db import connection
from openai import OpenAI


class SQLAgent:
    
    def __init__(self):
        """Initialize SQL Agent with Smart SQL features"""
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.view_name = "mv_compound_cards"
        
        # Cost tracking
        self.total_cost = 0.0
        
        # Database schema for LLM context
        self.schema = self._get_schema()
        
        # Initialize OpenAI client
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
            print("✅ SQL Agent initialized with Smart SQL")
        else:
            self.client = None
            print("⚠️ No OpenAI API key - SQL Agent disabled")
    
    def _get_schema(self) -> str:
        """Get database schema for LLM"""
        return """
mv_compound_cards materialized view columns:

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
- list_count (integer): Number of suspect lists

**Computed:**
- name_bucket (integer): 0=letter, 1=number, 2=other
- name_is_clean (boolean): Clean name flag
"""
    
    def answer(self, user_message: str) -> dict:
        """
        Answer user question with Smart SQL Agent
        
        Features:
        1. Pre-check if SQL-relevant
        2. Auto-discover synonyms
        3. Generate ranked SQL (exact match first)
        4. Handle typos
        5. Format results naturally
        """
        start_time = time.time()
        
        print(f"\n{'='*60}")
        print(f"🤖 Smart SQL Agent Query: {user_message}")
        print(f"{'='*60}")
        
        # Check if LLM available
        if not self.api_key or not self.client:
            return self._no_llm_response()
        
        # ========================================
        # STEP 1: PRE-CHECK IF SQL-RELEVANT
        # ========================================
        is_relevant = self._is_sql_relevant(user_message)
        
        if not is_relevant:
            print("⏭️  Question not relevant to chemical database")
            return {
                'found': False,
                'answer': None,
                'result_count': 0,
                'timing': {
                    'generation_ms': 0,
                    'execution_ms': 0,
                    'formatting_ms': 0,
                    'total_ms': (time.time() - start_time) * 1000
                },
                'cost': {
                    'generation': 0,
                    'formatting': 0,
                    'total': 0
                }
            }
        
        # ========================================
        # STEP 2: GENERATE SMART SQL WITH SYNONYMS & RANKING
        # ========================================
        gen_start = time.time()
        smart_result = self._generate_smart_sql(user_message)
        gen_time = time.time() - gen_start
        gen_cost = 0.0003  # Slightly higher due to synonym discovery
        
        if not smart_result or not smart_result.get('sql_query'):
            print("⚠️ Failed to generate smart SQL")
            return self._default_llm_response(user_message, gen_cost, gen_time)
        
        sql_query = smart_result['sql_query']
        main_term = smart_result.get('main_term', '')
        synonyms = smart_result.get('synonyms', [])
        
        print(f"🎯 Main term: {main_term}")
        print(f"🔄 Synonyms: {synonyms}")
        print(f"✅ Generated Smart SQL")
        print(f"📝 SQL Query:\n{sql_query}")
        
        # ========================================
        # STEP 3: EXECUTE SQL
        # ========================================
        exec_start = time.time()
        results, error = self._execute_query(sql_query)
        exec_time = time.time() - exec_start
        
        if error:
            print(f"⚠️ SQL execution error: {error}")
            return self._default_llm_response(user_message, gen_cost, gen_time)
        
        if not results:
            print("⚠️ No results found")
            return self._no_results_response(
                sql_query, main_term, synonyms, gen_cost, gen_time, exec_time
            )
        
        print(f"✅ Found {len(results)} results")
        
        # ========================================
        # STEP 4: FORMAT RESULTS WITH RANKING INFO
        # ========================================
        format_start = time.time()
        
        # ✅ NEW: Pass query_type and requested_field to formatter
        query_type = smart_result.get('query_type', 'search')
        requested_field = smart_result.get('requested_field', None)
        
        answer = self._format_smart_results(
            user_message, results, main_term, synonyms, query_type, requested_field
        )
        format_time = time.time() - format_start
        format_cost = 0.00015
        
        total_time = time.time() - start_time
        total_cost = gen_cost + format_cost
        
        print(f"⏱️  Total: {total_time*1000:.0f}ms")
        print(f"💰 Cost: ${total_cost:.6f}")
        
        return {
            'found': True,
            'answer': answer,
            'sql_query': sql_query,
            'main_term': main_term,
            'synonyms': synonyms,
            'result_count': len(results),
            'results': results,  # ✅ ADDED: Store actual results
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
    
    def _is_sql_relevant(self, user_message: str) -> bool:
      
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a classifier. Determine if a question is about chemical database queries.\n\n"
                            "Answer YES if question asks about:\n"
                            "- Chemical compounds, names, properties\n"
                            "- CAS numbers, SMILES, InChIKey, molecular identifiers\n"
                            "- Mass, molecular weight, chemical properties\n"
                            "- Counting/listing chemicals (e.g., 'how many X', 'list all X')\n"
                            "- Finding specific compounds or categories\n"
                            "- Searching for pesticides, herbicides, pharmaceuticals, etc.\n"
                            "- Database searches for chemicals\n"
                            "- Queries like 'find', 'search', 'show', 'list' for chemicals\n\n"
                            "Answer NO if question asks about:\n"
                            "- Authors, researchers, publications, papers\n"
                            "- Methodology, protocols, procedures\n"
                            "- General knowledge about concepts (what is X? explain Y?)\n"
                            "- Platform features, documentation, how-to guides\n"
                            "- Unrelated topics\n\n"
                            "IMPORTANT EXAMPLES:\n"
                            "YES: 'how many pesticides do we have' (counting chemicals)\n"
                            "YES: 'find compounds with benzene' (searching chemicals)\n"
                            "YES: 'list all PFAS' (listing chemicals)\n"
                            "NO: 'what is a pesticide?' (definition/concept)\n"
                            "NO: 'how do pesticides work?' (mechanism/theory)\n\n"
                            "Respond with ONLY 'YES' or 'NO'"
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Question: {user_message}\n\nIs this a chemical database query?"
                    }
                ],
                temperature=0.0,
                max_tokens=5
            )
            
            answer = response.choices[0].message.content.strip().upper()
            is_relevant = answer == "YES"
            
            print(f"📊 SQL Relevance: {'✅ YES' if is_relevant else '❌ NO'}")
            return is_relevant
            
        except Exception as e:
            print(f"⚠️ Relevance check failed: {e}")
            return True  # Fail-safe: assume relevant
    
    def _generate_smart_sql(self, user_message: str) -> dict:
        try:
            # ✅ FIXED: Use triple quotes to avoid f-string issues
            system_prompt = """You are an expert SQL generator for chemical compound databases.

DATABASE SCHEMA:
""" + self.schema + """

═══════════════════════════════════════════════════════════════
QUERY TYPE DETECTION
═══════════════════════════════════════════════════════════════

**1️⃣ FIELD VALUE QUERY** - User asks for specific column value:
   Patterns: "what is [FIELD] of [COMPOUND]", "[COMPOUND]'s [FIELD]", "show [FIELD] for [COMPOUND]"
   
**2️⃣ SEARCH QUERY** - User searches for compounds:
   Patterns: "how many [TYPE]", "find [TYPE]", "compounds with [TERM]"

═══════════════════════════════════════════════════════════════
AVAILABLE FIELDS
═══════════════════════════════════════════════════════════════

**Columns:** ns_id, cas, inchikey, dtxsid, name, name_lc, mass_num, xlogp_num, smiles, list_count, name_bucket, name_is_clean, pc_record_id, compound_id

**Field Aliases:**
- "mass", "weight" → mass_num
- "CAS number" → cas
- "xlogp", "logp" → xlogp_num
- "count", "list count" → list_count

⚠️ CRITICAL: list_count, mass_num, cas are FIELD NAMES, not compound names!

═══════════════════════════════════════════════════════════════
SQL GENERATION
═══════════════════════════════════════════════════════════════

**FOR FIELD VALUE QUERIES:**
```sql
SELECT name, [requested_field] 
FROM mv_compound_cards 
WHERE name_lc = LOWER('[compound]')
LIMIT 1;
```

**FOR SEARCH QUERIES:**
```sql
SELECT *, 
  CASE 
    WHEN name_lc = '[exact_term]' THEN 1
    WHEN name_lc LIKE '[term]%' THEN 2
    WHEN name_lc IN ('[synonym1]', '[synonym2]') THEN 3
    WHEN name_lc LIKE '%[term]%' THEN 5
    [more synonyms]
    ELSE 10
  END AS match_priority
FROM mv_compound_cards
WHERE name_lc LIKE '%[term]%' OR [synonym conditions]
ORDER BY match_priority ASC, name ASC
LIMIT 50;
```

Rules:
- Field queries: LIMIT 1, exact match, specific field only
- Search queries: LIMIT 50, priority ranking, SELECT *, include synonyms
- NEVER use COUNT(*) - always return data rows
- Use name_lc for all comparisons

═══════════════════════════════════════════════════════════════
EXAMPLES
═══════════════════════════════════════════════════════════════

**Example 1 - Field Value:**
User: "what is the list_count of atrazine"
{
  "query_type": "field_value",
  "requested_field": "list_count",
  "main_term": "atrazine",
  "synonyms": [],
  "sql_query": "SELECT name, list_count FROM mv_compound_cards WHERE name_lc = 'atrazine' LIMIT 1;",
  "explanation": "Returns list_count field value for Atrazine"
}

**Example 2 - Field with Alias:**
User: "show me atrazine's CAS number"
{
  "query_type": "field_value",
  "requested_field": "cas",
  "main_term": "atrazine",
  "synonyms": [],
  "sql_query": "SELECT name, cas FROM mv_compound_cards WHERE name_lc = 'atrazine' LIMIT 1;",
  "explanation": "Returns CAS field for Atrazine"
}

**Example 3 - Search:**
User: "how many pesticides do we have"
{
  "query_type": "search",
  "requested_field": null,
  "main_term": "pesticide",
  "synonyms": ["insecticide", "herbicide", "fungicide"],
  "sql_query": "SELECT *, CASE WHEN name_lc = 'pesticide' THEN 1 WHEN name_lc LIKE 'pesticide%' THEN 2 WHEN name_lc IN ('insecticide', 'herbicide', 'fungicide') THEN 3 WHEN name_lc LIKE '%pesticide%' THEN 5 WHEN name_lc LIKE '%insecticide%' THEN 6 WHEN name_lc LIKE '%herbicide%' THEN 6 WHEN name_lc LIKE '%fungicide%' THEN 6 ELSE 10 END AS match_priority FROM mv_compound_cards WHERE name_lc LIKE '%pesticide%' OR name_lc LIKE '%insecticide%' OR name_lc LIKE '%herbicide%' OR name_lc LIKE '%fungicide%' ORDER BY match_priority ASC, name ASC LIMIT 50;",
  "explanation": "Returns all pesticides with synonyms and ranking"
}

═══════════════════════════════════════════════════════════════
RESPONSE FORMAT
═══════════════════════════════════════════════════════════════

Return JSON only (no markdown):
{
  "query_type": "field_value" or "search",
  "requested_field": "field_name" or null,
  "main_term": "search term or compound name",
  "synonyms": ["list of synonyms"],
  "sql_query": "the SQL query",
  "explanation": "brief reasoning"
}
"""
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Generate smart SQL for: {user_message}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=800
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Validate
            if 'sql_query' not in result:
                return None
            
            # Force correct table name (just in case)
            sql = result['sql_query']
            sql = sql.replace('CompoundView', 'mv_compound_cards')
            sql = sql.replace('compoundview', 'mv_compound_cards')
            result['sql_query'] = sql
            
            return result
            
        except Exception as e:
            print(f"⚠️ Smart SQL generation error: {e}")
            # Fallback to simple SQL
            return self._generate_simple_sql_fallback(user_message)
    
    def _generate_simple_sql_fallback(self, user_message: str) -> dict:
        """Fallback: Generate simple SQL without synonyms"""
        try:
            # Extract likely search term
            words = user_message.lower().split()
            search_terms = []
            
            skip_words = ['find', 'search', 'show', 'get', 'list', 'how', 'many', 
                         'do', 'we', 'have', 'the', 'a', 'an', 'all', 'with']
            
            for word in words:
                clean = word.strip('.,!?;:')
                if clean and clean not in skip_words:
                    search_terms.append(clean)
            
            if not search_terms:
                return None
            
            main_term = search_terms[0]
            
            # ✅ ALWAYS return full data, never COUNT
            sql_query = f"SELECT * FROM mv_compound_cards WHERE name_lc LIKE '%{main_term}%' ORDER BY name ASC LIMIT 50;"
            
            return {
                'main_term': main_term,
                'synonyms': [],
                'sql_query': sql_query,
                'explanation': 'Simple search fallback'
            }
            
        except Exception as e:
            print(f"⚠️ Fallback SQL error: {e}")
            return None
    
    def _execute_query(self, sql_query: str):
        """Execute SQL query safely"""
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql_query)
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()
                results = [dict(zip(columns, row)) for row in rows]
                return results, None
        except Exception as e:
            return None, str(e)
    
    def _format_smart_results(self, question: str, results: list, 
                              main_term: str, synonyms: list,
                              query_type: str = 'search',
                              requested_field: str = None) -> str:
        """Format results with priority grouping"""
        try:
            # ============================================================
            # ✅ NEW: Handle FIELD VALUE queries
            # ============================================================
            if query_type == 'field_value' and requested_field and len(results) > 0:
                result = results[0]  # Get first result
                compound_name = result.get('name', 'Unknown')
                field_value = result.get(requested_field, 'N/A')
                
                # Format nicely based on field type
                if requested_field == 'list_count':
                    return f"The **list_count** for **{compound_name}** is: **{field_value}**"
                elif requested_field == 'cas':
                    return f"The **CAS number** for **{compound_name}** is: **{field_value}**"
                elif requested_field == 'mass_num':
                    return f"The **molecular mass** of **{compound_name}** is: **{field_value} Da**"
                elif requested_field == 'xlogp_num':
                    return f"The **logP** of **{compound_name}** is: **{field_value}**"
                elif requested_field == 'inchikey':
                    return f"The **InChIKey** for **{compound_name}** is: `{field_value}`"
                elif requested_field == 'smiles':
                    return f"The **SMILES** for **{compound_name}** is: `{field_value}`"
                else:
                    # Generic field
                    return f"The **{requested_field}** for **{compound_name}** is: **{field_value}**"
            
            question_lower = question.lower()
            wants_count = any(word in question_lower for word in ['how many', 'count', 'number of'])
            
            # If user wants count, show count + preview
            if wants_count and len(results) > 0:
                count = len(results)
                synonym_text = f" (including synonyms: {', '.join(synonyms[:3])})" if synonyms else ""
                
                preview_parts = [
                    f"✅ Found **{count}** compounds matching **{main_term}**{synonym_text} in the database.",
                    "",
                    "**Preview:**"
                ]
                
                for i, r in enumerate(results[:5], 1):
                    name = r.get('name', 'N/A')
                    preview_parts.append(f"{i}. {name}")
                
                if count > 5:
                    preview_parts.append(f"... and {count - 5} more")
                    preview_parts.append("")
                    preview_parts.append("💡 Say 'show all' to see complete list")
                
                return "\n".join(preview_parts)
            
            # Otherwise, show detailed results
            # Separate by priority if available
            exact_matches = []
            synonym_matches = []
            
            for result in results:
                priority = result.get('match_priority', 10)
                
                if priority <= 2:  # Exact or starts with user term
                    exact_matches.append(result)
                else:
                    synonym_matches.append(result)
            
            # Build answer
            answer_parts = []
            
            # Exact matches section
            if exact_matches:
                answer_parts.append(
                    f"✅ Found **{len(exact_matches)}** exact matches for **{main_term}**:"
                )
                
                for i, r in enumerate(exact_matches[:10], 1):
                    name = r.get('name', 'N/A')
                    cas = r.get('cas', 'N/A')
                    mass = r.get('mass_num', 'N/A')
                    
                    answer_parts.append(
                        f"{i}. **{name}** (CAS: {cas}, Mass: {mass})"
                    )
                
                if len(exact_matches) > 10:
                    answer_parts.append(
                        f"   ... and {len(exact_matches) - 10} more exact matches"
                    )
            
            # Synonym matches section
            if synonym_matches and synonyms:
                answer_parts.append(
                    f"\n📚 Also found **{len(synonym_matches)}** related compounds "
                    f"(synonyms: {', '.join(synonyms[:3])}):"
                )
                
                for i, r in enumerate(synonym_matches[:5], 1):
                    name = r.get('name', 'N/A')
                    answer_parts.append(f"{i}. {name}")
                
                if len(synonym_matches) > 5:
                    answer_parts.append(
                        f"   ... and {len(synonym_matches) - 5} more"
                    )
            
            # Total
            total = len(results)
            if total > 15:
                answer_parts.append(
                    f"\n**Total: {total} compounds** (showing top results)"
                )
            
            return "\n".join(answer_parts)
            
        except Exception as e:
            print(f"⚠️ Formatting error: {e}")
            return self._format_results_simple(results)
    
    def _format_results_simple(self, results: list) -> str:
        """Simple fallback formatting"""
        if not results:
            return "No results found."
        
        answer = f"Found {len(results)} compound(s):\n\n"
        
        for i, r in enumerate(results[:10], 1):
            name = r.get('name', 'N/A')
            cas = r.get('cas', 'N/A')
            mass = r.get('mass_num', 'N/A')
            
            answer += f"{i}. **{name}**\n"
            if cas != 'N/A':
                answer += f"   CAS: {cas}\n"
            if mass != 'N/A':
                answer += f"   Mass: {mass} Da\n"
        
        if len(results) > 10:
            answer += f"\n_...and {len(results) - 10} more_"
        
        return answer
    
    def _no_results_response(self, sql_query, main_term, synonyms, 
                            gen_cost, gen_time, exec_time):
        """Response when no results found"""
        
        # Build helpful message
        message_parts = [
            f"No results found for **{main_term}**"
        ]
        
        if synonyms:
            message_parts.append(
                f"(also searched: {', '.join(synonyms[:3])})"
            )
        
        message_parts.extend([
            "\n\n**Suggestions:**",
            "• Check spelling",
            "• Try a broader search term",
            "• Use chemical name instead of brand name",
            "• Try searching by CAS number or molecular formula"
        ])
        
        return {
            'found': False,
            'answer': "\n".join(message_parts),
            'sql_query': sql_query,
            'main_term': main_term,
            'synonyms': synonyms,
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
        """Fallback response when SQL fails"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a chemistry assistant."},
                    {"role": "user", "content": f"Brief answer for NORMAN chemical database question: {question}"}
                ],
                temperature=0.5,
                max_tokens=150
            )
            
            answer = response.choices[0].message.content.strip()
            
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
                    'formatting': 0.0001,
                    'total': gen_cost + 0.0001
                }
            }
        except Exception as e:
            print(f"⚠️ Fallback error: {e}")
            return self._no_llm_response()
    
    def _no_llm_response(self):
        """Response when no LLM available"""
        return {
            'found': False,
            'answer': "OpenAI API key required for database queries. Please check the FAQ or documentation.",
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
