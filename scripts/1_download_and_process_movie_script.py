

url = "https://imsdb.com/scripts/Big-Lebowski,-The.html"

# download site
import requests
from bs4 import BeautifulSoup

response = requests.get(url)
soup = BeautifulSoup(response.text, "html.parser")
# find the script in class "scrtext"
script_parent = soup.find("td", class_="scrtext")
# get script.pre.pre child
script = script_parent.find("pre").find("pre")

raw_text = script.text

result = []

for line in script:
    line_text = line.text
    line_text = line_text.lstrip('\r\n')

    if line_text == '':
        continue
    # Title
    elif line_text == '\t\t\tTHE BIG LEBOWSKI\r\n':
        continue
    # If line_text does not start with a tab, it's probably an action
    elif not line_text.startswith('\t\t'):
        result.append({
            'type': 'action',
            # strip multiple instances of \r\n
            'text': line_text.strip('\r\n')
        })
    elif line.name == 'b':
        print(line_text)


for item in result:
    if item['type'] == 'action':
        print(f"Action: {item['text']}")

# lines = raw_text.split('\n')
# html_output = []
# for line in lines:
#     if line.startswith('<b>') and line.endswith('</b>'):
#         # Handle headings
#         html_output.append(f'<div class="script-heading">{line[3:-4]}</div>')
#     elif line.strip().startswith('VOICE-OVER'):
#         # Handle character dialogue
#         html_output.append('<div class="voice-over">')
#         html_output.append(f'<div class="character">{line.strip()}</div>')
#     elif line.startswith('\t\t'):
#         # Handle dialogue lines
#         html_output.append(f'<div class="dialogue-line">{line.strip()}</div>')
#     elif line == '' or line == '\n' or line == '\r':
#         # Handle empty lines
#         html_output.append('<br>')
#     else:
#         # Handle action lines
#         html_output.append(f'<div class="action">{line}</div>')
# result = '\n'.join(html_output)