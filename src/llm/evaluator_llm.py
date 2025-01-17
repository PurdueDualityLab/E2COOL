from dotenv import load_dotenv
import json
from openai import OpenAI
import os
import time
from utils import Logger
import sys

load_dotenv()
openai_key = os.getenv('API_KEY')

logger = Logger("logs", sys.argv[2]).logger

assistant_prompt = f"""
    You are a code optimization and energy efficiency expert. Evaluate the following current code snippet in terms of time complexity, space complexity, energy usage, and performance, considering both the original and optimized code. Please provide a comprehensive analysis of the code's efficiency, energy consumption, and suggest further optimizations. Your feedback should include:

    1. **Current Code Behavior**:
    - Explain how the current code functions, highlighting its design, algorithm choices, and any assumptions it makes.
    
    2. **Inefficiencies and Bottlenecks**:
    - Identify potential inefficiencies in terms of time complexity (e.g., algorithm choice) and space complexity (e.g., memory usage).
    - Highlight any specific patterns or functions that are likely to consume excessive energy or computational resources.
    
    3. **Energy-Efficiency Specific Analysis**:
    - Analyze the energy consumption of the current code and identify why certain parts of the code might be consuming more energy compared to the optimized version. Look for energy-heavy operations such as frequent memory allocations, disk I/O, or inefficient loops.
    
    4. **Comparison to Best Optimized Code**:
    - Compare the current code with the best optimized code (lowest energy usage) provided. Highlight key differences that contribute to energy efficiency, such as:
        - Use of more efficient data structures or algorithms.
        - Modifications that reduce energy-intensive operations.
        - Opportunities to utilize hardware more efficiently (e.g., parallelism, vectorization, etc.).

    5. **Improvement Suggestions**:
    - Provide step-by-step suggestions for improving the current code, with a focus on reducing energy consumption, maintaining or improving runtime performance, and preserving readability.
    - Suggest any algorithmic improvements or refactorings that could help save energy. Recommend alternative approaches (e.g., swapping to a more energy-efficient algorithm).
    - Provide concrete code examples of how the current code could be refactored to reduce energy usage.

    6. **Energy-Specific Metrics and Best Practices**:
    - Suggest best practices and coding patterns for energy-efficient code, particularly focusing on areas where the current code deviates from these principles.
    - Point out potential areas where energy could be saved, such as reducing CPU-bound tasks, optimizing memory usage, or minimizing I/O operations.
    """

def create_evaluator_assistant():
    client = OpenAI(api_key=openai_key)
    assistant = client.beta.assistants.create(
            name="Evaluator",
            instructions=assistant_prompt,
            model="gpt-4o",
        )

    assistant_id = assistant.id
    return client, assistant_id

def evaluator_llm(llm, model_name, benchmark_info, client, assistant_id):

    #extract original
    original_source_code = benchmark_info["original"]["source_code"]
    original_avg_energy = benchmark_info["original"]["avg_energy"]
    original_avg_runtime = benchmark_info["original"]["avg_runtime"]

    lowest_soruce_code = benchmark_info["lowest_avg_energy"]["source_code"]
    lowest_avg_energy = benchmark_info["lowest_avg_energy"]["avg_energy"]
    lowest_avg_runtime = benchmark_info["lowest_avg_energy"]["avg_runtime"]

    current_source_code = benchmark_info["current"]["source_code"]  
    current_avg_energy = benchmark_info["current"]["avg_energy"]
    current_avg_runtime = benchmark_info["current"]["avg_runtime"]

    prompt = f"""
    Based on the provided instruction, evaluate the following current code snippet in terms of time complexity, space complexity, energy usage, and performance, considering both the original and optimized code. Please provide a comprehensive analysis of the code's efficiency, energy consumption, and suggest further optimizations.

    Here is the original code snippet:
    ```
    {original_source_code}
    ```
    Average energy usage: {original_avg_energy}
    Average run time: {original_avg_runtime}

    Here is the best code snippets(the lowest energy usage):
    ```
    {lowest_soruce_code}
    ```
    Average energy usage: {lowest_avg_energy}
    Average run time: {lowest_avg_runtime}

    Here is the current code snippiets that you are tasked to optimize:
    ```
    {current_source_code}
    ```
    Average energy usage: {current_avg_energy}
    Average run time: {current_avg_runtime}

    Please respond in natural language (English) with actionable suggestions for improving the current code's performance in terms of energy usage. Provide only the best code with the lowest energy usage.
    """

    if llm == "openai":
        # create a thread
        thread = client.beta.threads.create()

        # create a run
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread.id,
            assistant_id=assistant_id,
            instructions=prompt,
        )

        # check run status
        while run.status != 'completed':
            time.sleep(2)  # Wait for 2 seconds before checking again
            run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        
        # get message history
        messages = client.beta.threads.messages.list(
            thread_id=thread.id
        )
        evaluator_feedback = messages.data[0].content[0].text.value
        logger.info(f"Evaluator messages: {messages}")
    else:
        output = llm.chat(model=model_name, messages=messages)
        evaluator_feedback = output["message"]["content"]

    #write to file
    current_dir = os.path.join(os.path.dirname(__file__), "../runtime_logs")
    file_path = os.path.join(current_dir, "evaluator_feedback.txt")
    prompt_path = os.path.join(current_dir, "evaluator_prompt.txt")
    with open(prompt_path, "w+") as file:
        file.write(prompt)
    with open(file_path, "w+") as file:
        file.write(evaluator_feedback)
    
    return evaluator_feedback