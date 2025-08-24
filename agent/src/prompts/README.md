# AI Tutor Prompts

This directory contains all prompt templates used by the AI Tutor system.

## File Naming Convention

- `{function}_{type}.txt` - Where `function` is the AI capability and `type` is usually "system" or "user"
- Example: `question_generation_system.txt`, `question_generation_user.txt`

## Available Prompts

### Question Generation
- **question_generation_system.txt** - System prompt for generating educational questions
- **question_generation_user.txt** - User prompt trigger for question generation

### Explanation Generation
- **explanation_generation_system.txt** - System prompt for explaining answers and concepts

### Hint Generation
- **hint_generation_system.txt** - System prompt for providing helpful hints to students

## Usage

Prompts are loaded using the `PromptManager` utility:

```python
from utils.prompt_manager import prompt_manager

# Get a complete chat template
template = prompt_manager.get_question_generation_template()

# Load individual prompts
system_prompt = prompt_manager.load_prompt("question_generation_system")
```

## Template Variables

Prompts support variable substitution using `{variable_name}` syntax:

### Common Variables
- `{subject}` - Academic subject (math, science, etc.)
- `{topic}` - Specific topic within the subject
- `{difficulty}` - Question difficulty level
- `{question_type}` - Type of question (multiple_choice, etc.)
- `{context}` - Relevant context or source material
- `{skills}` - Target learning skills

## Best Practices

1. **Keep prompts focused** - Each prompt should have a single, clear purpose
2. **Use consistent formatting** - Follow the established JSON response format
3. **Include examples** - Show the expected output format in prompts
4. **Version control** - Changes to prompts should be tracked and tested
5. **Test thoroughly** - Always test prompt changes with the actual LLM

## Adding New Prompts

1. Create the prompt file(s) in this directory
2. Add corresponding methods to `PromptManager` class
3. Update this README with the new prompt information
4. Test the new prompts with actual API calls
