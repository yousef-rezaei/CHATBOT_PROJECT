"""
Prompt templates for RAG system
"""

COMPOUND_QA_PROMPT = """You are a chemical compound database assistant. Answer the user's question based on the provided compound information.

**Retrieved Compounds:**
{context}

**User Question:** {question}

**Instructions:**
- Answer based ONLY on the provided compound data
- If the data doesn't contain the answer, say "I don't have enough information"
- Be specific and cite compound names/CAS numbers
- Format numbers clearly
- Keep answers concise but complete

**Answer:**"""


COMPOUND_CONTEXT_TEMPLATE = """
Compound {index}:
- Name: {name}
- CAS: {cas}
- InChIKey: {inchikey}
- Molecular Mass: {mass} Da
- Lists: Found in {list_count} suspect lists
{smiles}
"""


NO_RESULTS_RESPONSE = """I couldn't find any compounds matching your query in the database. 

Try:
- Being more specific (e.g., "benzene" instead of "aromatic")
- Using identifiers (CAS number, InChIKey)
- Checking spelling
- Browsing FAQ categories for general information"""