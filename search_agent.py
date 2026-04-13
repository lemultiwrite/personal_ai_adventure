import ollama
import sys_msgs
import requests
import trafilatura
import urllib.parse
from bs4 import BeautifulSoup
from colorama import init, Fore, Style

init(autoreset=True)

assistant_convo = [sys_msgs.assistant_msg]

#
# search or not AI only returns true or false
# gemma4
#
def search_or_not():
    sys_msg = sys_msgs.search_or_not_msg

    response = ollama.chat(
        model='gemma4',
        messages=[{'role': 'system', 'content': sys_msg}, assistant_convo[-1]]
    )
    content = response['message']['content']
    print(f'{Fore.LIGHTRED_EX}SEARCH OR NOT RESULTS:{Style.RESET_ALL} {content}')

    return 'true' in content.lower()

#
# query generator provides best search terms to use
# llama3
#
def query_generator():
    sys_msg = sys_msgs.query_msg

    response = ollama.chat(
        model='llama3.1:8b',
        messages=[{'role': 'system', 'content': sys_msg}, assistant_convo[-1]]
    )
    print(f'{Fore.LIGHTRED_EX}SEARCH QUERY:{Style.RESET_ALL} {response["message"]["content"]}')
    return response['message']['content']

#
# gets first 10 search results
#
def duckduckgo_search(query):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
    }
    url = f'https://html.duckduckgo.com/html/?q={query}'
    response = requests.get(url, headers=headers)

    soup = BeautifulSoup(response.text, 'html.parser')
    results = []

    for i, result in enumerate(soup.find_all('div', class_='result'), start=0):
        if i > 9:
            break

        title_tag = result.find('a', class_='result__a')
        if not title_tag:
            continue

        link_raw = title_tag['href']
        parsed = urllib.parse.urlparse(link_raw)
        params = urllib.parse.parse_qs(parsed.query)
        link = params.get('uddg', [link_raw])[0]

        snippet_tag = result.find('a', class_='result__snippet')
        snippet = snippet_tag.text.strip() if snippet_tag else 'No description available'

        results.append({
            'id': i,
            'link': link,
            'search_description': snippet
        })

    print(f'{Fore.LIGHTRED_EX}OBTAINED TOP 10 RESULTS{Style.RESET_ALL}')
    return results

#
# determines best / most relevant source to use
# gemma4
#
def best_search_results(s_results, query):
    print(f'{Fore.LIGHTRED_EX}SEARCHING FOR BEST RESULT{Style.RESET_ALL}')
    sys_msg = sys_msgs.best_search_msg
    best_msg = (
        f'SEARCH_RESULTS: {s_results} \n'
        f'USER_PROMPT: {assistant_convo[-1]} \n'
        f'SEARCH_QUERY: {query}'
    )

    for _ in range(2):
        try:
            response = ollama.chat(
                model='gemma4',
                messages=[{'role': 'system', 'content': sys_msg}, {'role': 'user', 'content': best_msg}]
            )
            raw = response['message']['content'].strip()
            print(f'{Fore.LIGHTRED_EX}BEST SOURCE FOUND:{Style.RESET_ALL} {raw}')
            return int(raw)
        except Exception:
            print(f'{Fore.LIGHTRED_EX}FAILED TO LOCATE BEST SOURCE. TRYING AGAIN...{Style.RESET_ALL}')
            continue

    # Fall back to the id of the first available result
    return s_results[0]['id']

#
# extracts text from webpage
#
def scrape_webpage(url):
    try:
        downloaded = trafilatura.fetch_url(url=url)
        return trafilatura.extract(downloaded, include_formatting=True, include_links=True)
    except Exception:
        return None

#
# determine if extracted data is actually useful
# llama3
#
def contains_data_needed(search_content, query):
    sys_msg = sys_msgs.contains_data_msg
    needed_prompt = (
        f'PAGE_TEXT: {search_content} \n'
        f'USER_PROMPT: {assistant_convo[-1]} \n'
        f'SEARCH_QUERY: {query}'
    )

    response = ollama.chat(
        model='llama3.1:8b',
        messages=[{'role': 'system', 'content': sys_msg}, {'role': 'user', 'content': needed_prompt}]
    )

    content = response['message']['content']
    print(f'{Fore.LIGHTRED_EX}CONTAINS DATA NEEDED:{Style.RESET_ALL} {content}')
    return 'true' in content.lower()

#
# orchestrates search pipeline
#
def ai_search():
    context = None
    print(f'{Fore.LIGHTRED_EX}GENERATING SEARCH QUERY.{Style.RESET_ALL}')
    search_query = query_generator().strip('"')

    search_results = duckduckgo_search(search_query)

    while search_results:
        # FIX: best_search_results returns an 'id' value, not a list index.
        # Look up the result by its stable id instead of using it as a list index directly.
        best_id = best_search_results(s_results=search_results, query=search_query)
        result = next((r for r in search_results if r['id'] == best_id), None)

        if result is None:
            print(f'{Fore.LIGHTRED_EX}FAILED TO SELECT BEST SEARCH RESULT, SKIPPING.{Style.RESET_ALL}')
            search_results.pop(0)
            continue

        page_link = result['link']
        search_results.remove(result)

        page_text = scrape_webpage(page_link)

        if page_text and contains_data_needed(search_content=page_text, query=search_query):
            context = page_text
            break

    return context

#
# streaming assistant response
# gemma4
#
def stream_assistant_response():
    global assistant_convo
    response_stream = ollama.chat(model='gemma4', messages=assistant_convo, stream=True)
    complete_response = ''
    print('ASSISTANT:')

    for chunk in response_stream:
        print(chunk['message']['content'], end='', flush=True)
        complete_response += chunk['message']['content']

    assistant_convo.append({'role': 'assistant', 'content': complete_response})
    print('\n')
    return complete_response

#
#
def main():
    global assistant_convo

    while True:
        prompt = input('USER: \n')
        assistant_convo.append({'role': 'user', 'content': prompt})

        if search_or_not():
            context = ai_search()
            assistant_convo = assistant_convo[:-1]

            if context:
                prompt = f'SEARCH RESULT: {context} \n\nUSER_PROMPT: {prompt}'
            else:
                prompt = (
                    f'USER PROMPT: \n{prompt} \n\nFAILED SEARCH: \nThe '
                    'AI search model was unable to extract any reliable data. Explain that '
                    'and ask if the user would like you to search again or respond '
                    'without web search context. Do not respond with anything but this request.'
                )

            assistant_convo.append({'role': 'user', 'content': prompt})

        response = stream_assistant_response()

        # FIX: this block was un-indented, causing stream_assistant_response()
        # to fire on every loop iteration instead of only on forced retries.
        if response.strip() == '0':
    print(f'{Fore.LIGHTRED_EX}ASSISTANT NEEDS MORE DATA, FORCING SEARCH...{Style.RESET_ALL}')
    
    original_prompt = assistant_convo[-2]['content']  # grab user msg before slicing
    assistant_convo = assistant_convo[:-2]
    
    context = ai_search()

    if context:
        forced_prompt = f'SEARCH RESULT: {context} \n\nUSER_PROMPT: {original_prompt}'
    else:
        forced_prompt = (
            f'USER PROMPT: \n{original_prompt} \n\nFAILED SEARCH: \nThe '
            'AI search model was unable to extract any reliable data. Explain that '
            'and ask if the user would like you to search again.'
        )

    assistant_convo.append({'role': 'user', 'content': forced_prompt})
    stream_assistant_response()

if __name__ == '__main__':
    main()
