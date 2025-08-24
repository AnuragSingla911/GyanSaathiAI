"""
Prompt management utilities for AI Tutor Agent
"""

import os
from pathlib import Path
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate


class PromptManager:
    """Manages prompt templates loaded from files"""
    
    def __init__(self):
        self.prompts_dir = Path(__file__).parent.parent / "prompts"
        self._prompt_cache = {}
    
    def load_prompt(self, prompt_name: str) -> str:
        """Load a prompt template from file"""
        if prompt_name in self._prompt_cache:
            return self._prompt_cache[prompt_name]
        
        prompt_file = self.prompts_dir / f"{prompt_name}.txt"
        
        if not prompt_file.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
        
        with open(prompt_file, 'r', encoding='utf-8') as f:
            prompt_content = f.read().strip()
        
        # Cache the prompt
        self._prompt_cache[prompt_name] = prompt_content
        return prompt_content
    
    def get_question_generation_template(self) -> ChatPromptTemplate:
        """Get the chat prompt template for question generation"""
        system_prompt = self.load_prompt("question_generation_system")
        user_prompt = self.load_prompt("question_generation_user")
        
        return ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", user_prompt)
        ])
    
    def get_explanation_generation_template(self) -> ChatPromptTemplate:
        """Get the chat prompt template for explanation generation"""
        # This can be added later when we need explanation prompts
        system_prompt = """You are an expert educational tutor. Provide a clear, 
        detailed explanation for the given question and answer."""
        
        return ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "Explain this question: {question}\nCorrect answer: {answer}")
        ])
    
    def list_available_prompts(self) -> list:
        """List all available prompt files"""
        if not self.prompts_dir.exists():
            return []
        
        return [f.stem for f in self.prompts_dir.glob("*.txt")]
    
    def reload_prompts(self):
        """Clear the cache and reload all prompts"""
        self._prompt_cache.clear()


# Global instance
prompt_manager = PromptManager()
