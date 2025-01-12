from dotenv import load_dotenv
from openai import OpenAI
import os
from pydantic import BaseModel
import sys
from utils import Logger

load_dotenv()

openai_key = os.getenv('API_KEY')
USER_PREFIX = os.getenv('USER_PREFIX')

logger = Logger("logs", sys.argv[2]).logger

with open(f"{USER_PREFIX}/src/llm/llm_prompts/generator_prompt.txt", "r") as file:
    prompt = file.read()

def llm_optimize(client, model_name, filename, optim_iter):

    # get original code
    source_path = f"{USER_PREFIX}/llm/benchmarks_out/{filename.split('.')[0]}/{filename}"

    # get optimized file if is not first iteration
    if optim_iter != 0:
        source_path = f"{USER_PREFIX}/llm/benchmarks_out/{filename.split('.')[0]}/optimized_{filename}"

    # get lastly compiled code
    if filename.split('.')[1] == "compiled":
        source_path = f"{USER_PREFIX}/llm/benchmarks_out/{filename.split('.')[0]}/{filename}"
        filename = filename.split('.')[0] + "." + ('.'.join(filename.split('.')[2:]))
    
    with open(source_path, "r") as file:
        code_content = file.read()

    class Strategy(BaseModel):
        Pros: str
        Cons: str

    class OptimizationReasoning(BaseModel):
        analysis: str
        strategies: list[Strategy] 
        selected_strategy: str
        final_code: str

    #checking for evaluator feedback
    # Construct the absolute path to evaluator_feedback.txt
    feedback_file_path = os.path.abspath(f"{USER_PREFIX}/src/runtime_logs/evaluator_feedback.txt")

    if os.path.isfile(feedback_file_path):
        with open(feedback_file_path, 'r') as file:
            evaluator_feedback = file.read()
            evaluator_feedback = "Here's some suggestion on how you should optimize the code from the evaluator, keep these in mind when optimizing code\n" + evaluator_feedback
            logger.info("llm_optimize: got evaluator feedback")

    else:
        evaluator_feedback = ""
        logger.info("llm_optimize: First optimization, no evaluator feedback yet")

    # add code content to prompt
    optimize_prompt = prompt + f" {code_content}" + f" {evaluator_feedback}"

    with open(f"{USER_PREFIX}/src/runtime_logs/generator_prompt_log.txt", "w") as f:
        f.write(optimize_prompt)
    
    logger.info(f"llm_optimize: Generator LLM Optimizing ....")
    messages = [
                {
                    "role": "system", 
                    "content": "You are a helpful assistant. Think through the code optimizations strategies possible step by step"
                },
                {
                    "role": "user",
                    "content": optimize_prompt
                }
                ]
    if client == "openai":
        client = OpenAI(api_key=openai_key)
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=messages,
            response_format=OptimizationReasoning
        )
        final_code = completion.choices[0].message.parsed.final_code
    else:
        output = client.chat(model=model_name, messages=messages)
        final_code = output["message"]["content"]

    if final_code == "":
        logger.error("Error in llm completion")
        return
    
    # Remove code block delimiters
    final_code = final_code.replace("```cpp", "")
    final_code = final_code.replace("```", "")
    
    logger.info(f"llm_optimize: : writing optimized code to llm/benchmarks_out/{filename.split('.')[0]}/optimized_{filename}")
    destination_path = f"{USER_PREFIX}/llm/benchmarks_out/{filename.split('.')[0]}/optimized_{filename}"
    with open(destination_path, "w") as file:
        file.write(final_code)

    # Success code
    return 0

def handle_compilation_error(client, model_name, filename):
    with open(f"{USER_PREFIX}/llm/benchmarks_out/{filename.split('.')[0]}/optimized_{filename}", "r") as file:
        optimized_code = file.read()

    with open(f"{USER_PREFIX}/src/runtime_logs/regression_test_log.txt", "r") as file:
        error_message = file.read()
    

        class ErrorReasoning(BaseModel):
            analysis: str
            final_code: str
        
        compilation_error_prompt = f"""You were tasked with the task outlined in the following prompt: {prompt}. You returned the following optimized code: {optimized_code}. However, the code failed to compile with the following error message: {error_message}. Analyze the error message and explicitly identify the issue in the code that caused the compilation error. Then, consider if there's a need to use a different optimization strategy to compile successfully or if there are code changes which can fix this implementation strategy. Finally, update the code accordingly and ensure it compiles successfully. Ensure that the optimized code is both efficient and error-free and return it. """   
        
        logger.info("handle_compilation_error: promting for re-optimization")
        messages = [
                    {
                        "role": "system",
                        "content": "You are a code expert. Think through the code debugging strategies step by step."},
                    {
                        "role": "user",
                        "content": compilation_error_prompt
                    }
                    ]
        if client == "openai":
            client = OpenAI(api_key=openai_key)
            completion = client.beta.chat.completions.parse(
                model="gpt-4o-2024-08-06",
                messages=messages,
                response_format=ErrorReasoning
            )
            final_code = completion.choices[0].message.parsed.final_code
        else:
            output = client.chat(model=model_name, messages=messages)
            final_code = output["message"]["content"]

        # Remove code block delimiters
        final_code = final_code.replace("```cpp", "")
        final_code = final_code.replace("```", "")

        logger.info(f"handle_compilation_error: writing re-optimized code to optimized_{filename}")
        destination_path = f"{USER_PREFIX}/llm/benchmarks_out/{filename.split('.')[0]}"
        with open(destination_path+"/optimized_"+filename, "w") as file:
            file.write(final_code)

def handle_logic_error(client, model_name, filename):
    with open(f"{USER_PREFIX}/llm/benchmarks_out/{filename.split('.')[0]}/optimized_{filename}", "r") as file:
        optimized_code = file.read()

    with open(f"{USER_PREFIX}/src/runtime_logs/regression_test_log.txt", "r") as file:
        output_differences = file.read()
    
    class ErrorReasoning(BaseModel):
        analysis: str
        final_code: str
        
    #just prompting it to give output difference everytime
    logic_error_prompt = f"""You were tasked with the task outlined in the following prompt: {prompt}. You returned the following optimized code: {optimized_code}. However, the code failed to produce the same outputs as the original source code. Here are the output differences : {output_differences}. Analyze the source code and the optimized code and explicitly identify the potential reasons that caused the logic error. Then, consider if there's a need to use a different optimization strategy to match the outputs or if there are code changes which can fix this implementation strategy. Finally, update the code accordingly and ensure it will match the source code's outputs for any input. Ensure that the optimized code is both efficient and error-free and return it. """
    
    messages = [
                {
                    "role": "system",
                    "content": "You are a code expert. Think through the code debugging strategies step by step."},
                {
                    "role": "user",
                    "content": logic_error_prompt
                }
                ]
    if client == "openai":
        client = OpenAI(api_key=openai_key)
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=messages,
            response_format=ErrorReasoning
        )
        final_code = completion.choices[0].message.parsed.final_code
    else:
        output = client.chat(model=model_name, messages=messages)
        final_code = output["message"]["content"]

    # Remove code block delimiters
        final_code = final_code.replace("```cpp", "")
        final_code = final_code.replace("```", "")

    destination_path = f"{USER_PREFIX}/llm/benchmarks_out/{filename.split('.')[0]}"
    with open(destination_path+"/optimized_"+filename, "w") as file:
        file.write(final_code)
