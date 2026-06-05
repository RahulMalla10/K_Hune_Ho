from src.news_retriever import NewsRetriever
from src.agent_manager import AgentManager
from src.synthesizer import Synthesizer

def print_header():
    """Display the application header with styling."""
    print("\n" + "="*70)
    print("  K_HUNE_HORA? Neural News Analysis System")
    print("  Multi-Domain AI-Powered Topic Analysis")
    print("="*70)
    print("\nCommands: Enter a topic | Type 'exit' to quit\n")

def print_step(step_num: int, total_steps: int, message: str):
    print(f"\n[{step_num}/{total_steps}] {message}")

def print_success(message: str):
    print(f"  ✓ {message}")

def print_error(message: str):
    print(f"  ✗ {message}")

def print_separator():
    print("\n" + "="*70)

def main():
    print_header()
    
    # Initialize components
    retriever = NewsRetriever()
    agent_mgr = AgentManager()
    synthesizer = Synthesizer()
    
    while True:
        try:
            topic = input("> Topic: ").strip()
            
            if topic.lower() in ("exit", "quit"):
                print("\nExiting. Goodbye!\n")
                break
            
            if not topic:
                continue
            
            print_step(1, 3, f"Searching news for: '{topic}'")
            articles = retriever.search(topic)
            
            if not articles:
                print_error("No articles found. Try another topic.")
                continue
            
            print_success(f"Found {len(articles)} articles")
            
            print_step(2, 3, "Running 15 reasoning agents")
            agent_results = agent_mgr.run_all_agents(articles)
            
            print_step(3, 3, "Generating comprehensive report")
            report = synthesizer.final_report(topic, articles, agent_results)
            
            print_separator()
            print(report)
            print_separator()
            print()
            
        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Exiting gracefully.\n")
            break
        except Exception as e:
            print_error(f"An error occurred: {e}")
            print("Please try again or check your configuration.\n")

if __name__ == "__main__":
    main()