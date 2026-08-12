# spotify-rag

RAG chatbot that answers natural-language questions about your own Spotify listening history

Discuss your listening trends, favorite artists, and recommendations

# Example Queries

What are my top artists over x amount of time?
What genre's do I listen to the most?
What artist do I not listen to would fit with my preferences?

# Architecture / Stack

Flask backend
React frontend
Spotipy + OAuth
OpenAI embeddings
ChromaDB
Spotify API -> Ingestion -> embeddings -> ChromaDB -> retrieval -> LLM -> chat UI

# Constraints / Tradeoffs

Spotify deprecated Audio Features / Recommendations for new apps in 2024-2026, this app will use behavioral/categorical data instead

# Set up / How to Run

# Scope Boundaries

No playlist generation
No audio feature analysis
Single user, not multi tenant
