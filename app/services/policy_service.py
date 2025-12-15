"""
Policy Service: File-based RAG for business policies.

Loads policies from docs/policies/*.md and retrieves relevant ones based on keywords.
"""
import os
import re
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Policy directory
POLICIES_DIR = Path(__file__).parent.parent.parent / "docs" / "policies"

# Keyword mappings for each policy file
POLICY_KEYWORDS = {
    "privacy": {
        "keywords": ["privacy", "data", "information", "phone number", "email", "address", "why do you need", "personal", "safe", "share", "third party", "ndpr"],
        "priority": 1
    },
    "delivery": {
        "keywords": ["delivery", "shipping", "logistics", "fee", "location", "address", "ibadan", "lagos", "how much deliver", "distance", "pickup", "collect"],
        "priority": 2
    },
    "payment": {
        "keywords": ["payment", "pay", "paystack", "card", "transfer", "bank", "25k", "25000", "approval", "approve", "price", "amount", "total"],
        "priority": 2
    },
    "consultation": {
        "keywords": ["consultation", "consult", "dermatologist", "doctor", "skin analysis", "diagnose", "diagnosis", "prescription", "medical", "health"],
        "priority": 3
    },
    "safety": {
        "keywords": ["off topic", "not related", "help me with", "general question", "essay", "math", "news", "competitor", "jumia", "sephora"],
        "priority": 4
    },
    "product_recommendations": {
        "keywords": ["recommend", "suggestion", "alternative", "substitute", "instead", "similar", "like", "skin type", "oily", "dry"],
        "priority": 3
    },
    "returns_refunds": {
        "keywords": ["return", "refund", "money back", "wrong product", "damaged", "defective", "cancel", "cancellation", "exchange"],
        "priority": 2
    },
    "escalation": {
        "keywords": ["manager", "speak to", "talk to", "human", "complaint", "issue", "problem", "escalate", "help"],
        "priority": 3
    },
    "store_info": {
        "keywords": ["location", "address", "where", "shop", "store", "hours", "open", "close", "visit", "contact", "directions"],
        "priority": 2
    }
}


class PolicyService:
    """
    Service for loading and retrieving business policies.
    """
    
    def __init__(self):
        self.policies: Dict[str, str] = {}
        self.loaded = False
    
    def load_policies(self) -> None:
        """Load all policy files from disk."""
        if self.loaded:
            return
            
        if not POLICIES_DIR.exists():
            logger.warning(f"Policies directory not found: {POLICIES_DIR}")
            return
        
        for policy_file in POLICIES_DIR.glob("*.md"):
            policy_name = policy_file.stem
            try:
                content = policy_file.read_text(encoding="utf-8")
                self.policies[policy_name] = content
                logger.info(f"Loaded policy: {policy_name}")
            except Exception as e:
                logger.error(f"Failed to load policy {policy_name}: {e}")
        
        self.loaded = True
        logger.info(f"Loaded {len(self.policies)} policies")
    
    def get_policy(self, name: str) -> Optional[str]:
        """Get a specific policy by name."""
        self.load_policies()
        return self.policies.get(name)
    
    def search_policies(self, query: str, max_results: int = 2) -> List[Tuple[str, str]]:
        """
        Search for relevant policies based on a query.
        
        Args:
            query: User's message or query
            max_results: Maximum number of policies to return
            
        Returns:
            List of (policy_name, policy_content) tuples, sorted by relevance
        """
        self.load_policies()
        
        if not self.policies:
            return []
        
        query_lower = query.lower()
        scores: Dict[str, int] = {}
        
        # Score each policy based on keyword matches
        for policy_name, config in POLICY_KEYWORDS.items():
            keywords = config["keywords"]
            priority = config.get("priority", 5)
            
            score = 0
            for keyword in keywords:
                if keyword in query_lower:
                    # Longer keyword matches get higher scores
                    score += len(keyword.split())
            
            if score > 0:
                # Apply priority (lower priority number = higher importance)
                scores[policy_name] = score * (10 - priority)
        
        # Sort by score and return top results
        sorted_policies = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        results = []
        for policy_name, score in sorted_policies[:max_results]:
            if policy_name in self.policies:
                results.append((policy_name, self.policies[policy_name]))
        
        return results
    
    def get_policy_summary(self, name: str, max_lines: int = 20) -> Optional[str]:
        """
        Get a summarized version of a policy (first N lines).
        Useful for injecting into prompts without bloating.
        """
        content = self.get_policy(name)
        if not content:
            return None
        
        lines = content.split("\n")
        
        # Take first max_lines, prioritizing headers and key points
        summary_lines = []
        for line in lines[:max_lines * 2]:  # Look ahead a bit
            if line.strip():
                # Prioritize headers and bullet points
                if line.startswith("#") or line.startswith("-") or line.startswith("*"):
                    summary_lines.append(line)
                elif len(summary_lines) < max_lines:
                    summary_lines.append(line)
            
            if len(summary_lines) >= max_lines:
                break
        
        return "\n".join(summary_lines)
    
    def get_relevant_context(self, query: str, max_chars: int = 2000) -> str:
        """
        Get a combined, relevant policy context for a query.
        
        Args:
            query: User's message
            max_chars: Maximum characters to return
            
        Returns:
            Combined policy context as a string
        """
        results = self.search_policies(query, max_results=2)
        
        if not results:
            return ""
        
        context_parts = []
        total_chars = 0
        
        for name, content in results:
            # Use summary for better token efficiency
            summary = self.get_policy_summary(name, max_lines=15)
            if summary:
                header = f"--- {name.replace('_', ' ').title()} Policy ---\n"
                section = header + summary
                
                if total_chars + len(section) <= max_chars:
                    context_parts.append(section)
                    total_chars += len(section)
                else:
                    # Truncate to fit
                    remaining = max_chars - total_chars
                    if remaining > 100:
                        context_parts.append(section[:remaining])
                    break
        
        return "\n\n".join(context_parts)


# Singleton instance
policy_service = PolicyService()


def get_policy_for_query(query: str) -> str:
    """
    Convenience function to get relevant policy context for a query.
    
    Args:
        query: User's message or question
        
    Returns:
        Relevant policy context string
    """
    return policy_service.get_relevant_context(query)
