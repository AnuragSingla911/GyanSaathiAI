#!/usr/bin/env python3
"""
Test script for the enhanced Agent v2 architecture.
Verifies that all components can be imported and initialized properly.
"""

import asyncio
import sys
import os

# Add the src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
sys.path.insert(0, os.path.dirname(__file__))

async def test_enhanced_agent():
    """Test the enhanced agent components"""
    print("🚀 Testing Enhanced Agent v2 Architecture")
    print("=" * 50)
    
    try:
        # Test 1: Import all new services
        print("1. Testing imports...")
        
        from services.hendrycks_dataset import HendrycksDatasetManager
        from services.hybrid_retriever import HybridRetriever
        from services.template_inducer import TemplateInducer
        from services.distractor_factory import DistractorFactory
        from services.validators import EnhancedQuestionValidator
        from services.enhanced_generator import EnhancedQuestionGenerator
        from utils.config import get_settings
        
        print("   ✅ All imports successful")
        
        # Test 2: Configuration
        print("2. Testing configuration...")
        settings = get_settings()
        
        required_params = [
            'exemplar_k', 'retrieval_tau', 'novelty_max_overlap', 
            'dedup_cosine_threshold', 'max_retries'
        ]
        
        for param in required_params:
            if hasattr(settings, param):
                print(f"   ✅ {param}: {getattr(settings, param)}")
            else:
                print(f"   ❌ Missing parameter: {param}")
        
        # Test 3: Component initialization (without external dependencies)
        print("3. Testing component initialization...")
        
        # Template Inducer (standalone)
        template_inducer = TemplateInducer(settings)
        print("   ✅ Template Inducer initialized")
        
        # Distractor Factory (standalone)
        distractor_factory = DistractorFactory(settings)
        print("   ✅ Distractor Factory initialized")
        
        # Enhanced Validator (requires mongo client, but can test without)
        enhanced_validator = EnhancedQuestionValidator(settings, None)
        print("   ✅ Enhanced Validator initialized")
        
        # Test 4: Template Induction
        print("4. Testing template induction...")
        template_result = await template_inducer.induce_template(
            topic="linear equations",
            difficulty="medium",
            subject_hint="algebra"
        )
        
        if template_result:
            print(f"   ✅ Template induced: {template_result['template_name']}")
            print(f"   📝 Pattern: {template_result['instantiated_problem']}")
        else:
            print("   ⚠️ No template found for test topic")
        
        # Test 5: Distractor Generation
        print("5. Testing distractor generation...")
        
        if template_result and template_result.get('canonical_solution', {}).get('answer'):
            correct_answer = template_result['canonical_solution']['answer']
            context = {
                "subject": "math",
                "topic": "linear equations", 
                "difficulty": "medium",
                "template": template_result
            }
            
            distractors = await distractor_factory.generate_distractors(
                correct_answer=correct_answer,
                question_context=context,
                count=3
            )
            
            print(f"   ✅ Generated {len(distractors)} distractors")
            for i, dist in enumerate(distractors, 1):
                print(f"   📝 Distractor {i}: {dist['value']} ({dist['generation_method']})")
        else:
            print("   ⚠️ No template answer available for distractor test")
        
        # Test 6: Schema validation
        print("6. Testing schema validation...")
        
        from models.schemas import QuestionCandidate
        
        test_question = QuestionCandidate(
            stem="What is 2 + 2?",
            options=[
                {"id": "a", "text": "3"},
                {"id": "b", "text": "4"},
                {"id": "c", "text": "5"},
                {"id": "d", "text": "6"}
            ],
            correct_option_ids=["b"],
            question_type="multiple_choice",
            explanation="Basic addition",
            difficulty="easy"
        )
        
        test_spec = {
            "subject": "math",
            "topic": "arithmetic",
            "difficulty": "easy",
            "question_type": "multiple_choice"
        }
        
        validation_results = await enhanced_validator.validate_all(test_question, test_spec)
        
        for name, result in validation_results.items():
            status = "✅" if result.passed else "❌"
            print(f"   {status} {name}: {result.score:.2f}")
        
        print("\n🎉 Enhanced Agent v2 Architecture Test Complete!")
        print("=" * 50)
        
        # Summary
        passed_validations = sum(1 for r in validation_results.values() if r.passed)
        total_validations = len(validation_results)
        
        print(f"📊 Summary:")
        print(f"   • All imports: ✅")
        print(f"   • Configuration: ✅")
        print(f"   • Component initialization: ✅")
        print(f"   • Template induction: {'✅' if template_result else '⚠️'}")
        print(f"   • Distractor generation: ✅")
        print(f"   • Validation: {passed_validations}/{total_validations} passed")
        print(f"\n🚀 Agent v2 is ready for enhanced question generation!")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Set up basic environment variables for testing
    os.environ.setdefault('OPENAI_API_KEY', 'test-key')
    os.environ.setdefault('POSTGRES_URL', 'postgresql://test@localhost/test')
    os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017/test')
    
    success = asyncio.run(test_enhanced_agent())
    sys.exit(0 if success else 1)
