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
        model = 'gemma4',
        messages=[{'role': 'system', 'content': sys_msg}, assistant_convo[-1]]
    )
    content = response['message']['content']
    print(f'{Fore.LIGHTRED_EX}SEARCH OR NOT RESULTS:{Style.RESET_ALL} {content}')

    if 'true' in content.lower():
        return True
    else:
        return False

#
# query generator provides best search terms to use
# llama3
#ple
def query_generator ():
    sys_msg = sys_msgs.query_msg
    #query_msg = f'CREATE A SEARCH QUERY FOR THIS PROMPT: \n{assistant_convo[-1]}'

    response = ollama.chat(
        model = 'llama3.1:8b',
        messages=[{'role': 'system', 'content': sys_msg}, assistant_convo[-1]]
    )
    print(f'{Fore.LIGHTRED_EX}SEARCH QUERY:{Style.RESET_ALL} {response['message']['content']}')
    return response ['message']['content']

#
# gets first 10 search results
#
def duckduckgo_search(query):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"

    }
    url = f'https://html.duckduckgo.com/html/?q={query}'
    response = requests.get(url, headers=headers)
    #requests.raise_for_status()

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
# determines best / most relevant source to extrapolate from
# gemma4
#
def best_search_results(s_results, query):
    print(f'{Fore.LIGHTRED_EX}SEARCHING FOR BEST RESULT{Style.RESET_ALL}')
    sys_msg = sys_msgs.best_search_msg
    best_msg = f'SEARCH_RESULTS: {s_results} \nUSER_PROMPT: {assistant_convo[-1]} \nSEARCH_QUERY: {query}'
    
    for _ in range(2):
        try:
            response = ollama.chat(
                model='gemma4',
                messages=[{'role': 'system', 'content': sys_msg}, {'role': 'user', 'content': best_msg}]      
            )
            print(f'{Fore.LIGHTRED_EX}BEST SOURCE FOUND:{Style.RESET_ALL} {response['message']['content']}')
            return int(response['message']['content'])
        except:
            print(f'{Fore.LIGHTRED_EX} FAILED TO LOCATE BEST SOURCE. TRYING AGAIN...{Style.RESET_ALL}')
            continue
    
    return 0       

#
# extracts text from webpage
#
def scrape_webpage(url):
    try:
        downloaded = trafilatura.fetch_url(url=url)
        return trafilatura.extract(downloaded, include_formatting=True, include_links=True)
    except Exception as e:
        return None

#
# determine if extrapolated data is actually useful
# llama3
#
def contains_data_needed(search_content, query):
    sys_msg = sys_msgs.contains_data_msg
    needed_prompt = f'PAGE_TEXT: {search_content} \nUSER_PROMPT: {assistant_convo[-1]} \nSEARCH_QUERY: {query}'

    response = ollama.chat(
        model='llama3.1:8b',
        messages=[{'role': 'system', 'content': sys_msg}, {'role': 'user', 'content': needed_prompt}]
    )

    content = response['message']['content']
    print(f'{Fore.LIGHTRED_EX}CONTAINS DATA NEEDED:{Style.RESET_ALL} {response['message']['content']}')

    if 'true' in content.lower():
        return True
    else:
        return False

#
# does stuff and things so it works
#
def ai_search():
    context = None
    print(f'{Fore.LIGHTRED_EX}GENERATING SEARCH QUERY.{Style.RESET_ALL}')
    search_query = query_generator()

    if search_query[0] == '"':
        search_query = search_query[1:-1]

    search_results = duckduckgo_search(search_query)
    context_found = False

    while not context_found and len(search_results) > 0:
        best_result = best_search_results(s_results=search_results, query=search_query)
        try:
            page_link = search_results[best_result]['link']
        except:
            print(f'{Fore.LIGHTRED_EX}FAILED TO SELECT BEST SEARCH RESULT, TRYING AGAIN. {Style.RESET_ALL}')
            search_results.pop(0)
            continue
       
        page_text = scrape_webpage(page_link)
        search_results.pop(best_result)

        if page_text and contains_data_needed(search_content=page_text, query=search_query):
            context = page_text
            context_found = True
    
    return context

#
# outputting AI agent
# gemma4
#
def stream_assistant_response():
    global assistant_convo
    response_stream = ollama.chat(model='gemma4', messages=assistant_convo, stream=True)
    complete_response = ''
    print('ASSISTANT:')

    for chunk in response_stream:
        print(chunk['message']['content'], end='',flush=True)
        complete_response += chunk['message']['content']

    assistant_convo.append({'role': 'assistant', 'content':complete_response})
    print('\n\n')
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
                    'and ask if the user would likke you to search again or respond '
                    'without web search context. Do not respond if a search was needed '
                    'and you are getting this message with anything but the above request '
                    'of how the user would likek to proceed'
                )

        response = stream_assistant_response()

        if response.strip() == '0':
            print(f'{Fore.LIGHTRED_EX}ASSISTANT NEEDS MORE DATA, FORCING SEARCH...{Style.RESET_ALL}')
            context = ai_search()
            assistant_convo = assistant_convo[:-2]  # remove the '0' response and last user msg
            if context:
                forced_prompt = f'SEARCH RESULT: {context} \n\nUSER_PROMPT: {assistant_convo[-1]["content"]}'
            else:
                forced_prompt = (
                    f'USER PROMPT: \n{assistant_convo[:-1]["content"]} \n\nFAILED SEARCH: \nThe '
                    'AI search model was unable to extract any reliable data. Explain that '
                    'and ask if the user would like you to search again.'
                )
            assistant_convo.append({'role': 'user', 'content': forced_prompt})
        stream_assistant_response()

if __name__ == '__main__':
    main()