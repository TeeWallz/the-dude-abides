import re
import requests
from bs4 import BeautifulSoup
from dataclasses import asdict, dataclass
from typing import List, Optional, Iterator, Tuple
import json
from enum import Enum, auto
import logging
from sentence_splitter import SentenceSplitter

########################################################
# TODO:                                                # 
# - Adding Ids to each element for easier reference    #
# - How to reference a line of dialog in a script?     #
# - How to attach a timecode to a line of dialog?      #
# - If needed, find a different structure for the json #
########################################################

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
Splitter = SentenceSplitter(language='en')


class ElementType(Enum):
    ACTION = auto()
    CHARACTER = auto()
    LOCATION = auto()
    TRANSITION = auto()
    SCENE_HEADING = auto()
    PARENTHETICAL = auto()
    DIALOGUE = auto()
    def __str__(self):
        return self.name

@dataclass
class ScriptElement:
    element_type: ElementType
    content: str
    metadata: Optional[dict] = None

    def __json__(self):
        return {
            'element_type': self.element_type.name,
            'content': self.content,
            'metadata': self.metadata
        }

@dataclass
class Script:
    title: str
    elements: List[ScriptElement]

    def __post_init__(self):
        self.elements = []

    def add_element(self, element: ScriptElement):
        self.elements.append(element)

    def __iter__(self):
        return iter(self.elements)
    
    def __json__(self):
        return {
            'title': self.title,
            'elements': [element.__json__() for element in self.elements]
        }

class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ElementType):
            return obj.name
        return super().default(obj)

class ScriptParser:
    """A robust parser for IMSDB script pages that handles tab-based formatting."""
    
    def __init__(self):
        self.base_url = "https://imsdb.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text while preserving meaningful whitespace."""
        text = text.replace('\r', '').replace('\n', ' ')
        text = re.sub(r' +', ' ', text)  # Collapse multiple spaces
        return text.strip()
    
    def _get_indentation_level(self, line: str) -> Tuple[int, str]:
        """Determine the indentation level and clean the line."""
        original_line = line
        if not line:
            return 0, ""
            
        # Count tabs and leading spaces
        tabs = 0
        spaces = 0
        for char in line:
            if char == '\t':
                tabs += 1
            elif char == ' ':
                spaces += 1
            else:
                break
                
        # Convert spaces to tab equivalents (assuming 4 spaces = 1 tab)
        total_indent = tabs + (spaces // 4)
        cleaned_line = line[tabs + spaces:]
        
        return total_indent, cleaned_line
    
    def _extract_script_text(self, url: str) -> Optional[str]:
        """Extract raw script text from the IMSDB page."""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            script_parent = soup.find("td", class_="scrtext")
            if not script_parent:
                logger.error("Could not find script container")
                return None
                
            script = script_parent.find("pre").find("pre")
            return script.text if script else None
        except Exception as e:
            logger.error(f"Error extracting script text: {e}")
            return None

    def _get_element_type(self, raw_text: str, clean_text: str, indent_level: int) -> Optional[ElementType]:
        """Determine the type of script element based on the line content."""
        # count amoutn of tabs at the start of the string in raw_text
        if clean_text == "":
            return None
        elif indent_level == 0 and clean_text.isupper():
            return ElementType.SCENE_HEADING
        elif indent_level == 0:
            return ElementType.ACTION
        elif indent_level == 1:
            if clean_text.isupper():
                return ElementType.DIALOGUE
            else:
                return ElementType.ACTION
        elif indent_level == 2:
            if clean_text.startswith("(") and clean_text.endswith(")"):
                return ElementType.DIALOGUE
                # return ElementType.PARENTHETICAL
            else:
                return ElementType.DIALOGUE
        elif indent_level == 3:
            if clean_text.startswith("(") and clean_text.endswith(")"):
                return ElementType.DIALOGUE
                # return ElementType.PARENTHETICAL
        elif indent_level == 4:
            return ElementType.DIALOGUE
        elif indent_level == 5:
            return ElementType.TRANSITION
        elif indent_level == 6:
            return ElementType.TRANSITION
        else:
            # raise exception if the indent level is not recognized
            raise ValueError(f"Unrecognized indent level: {indent_level} for line: {raw_text}")

    def _convert_dialog_to_sentences(self, text: str) -> List[str]:
        """Convert dialogue text into sentences using the sentence splitter."""
        sentences = Splitter.split(text)
        return [sentence.strip() for sentence in sentences if sentence.strip()]


    def _parse_script_lines(self, raw_text: str) -> Iterator[ScriptElement]:
        """Parse raw script text into structured elements using indentation."""
        script = Script(title="Movie Title", elements=[])
        lines = raw_text.split('\r\n')
        read_title = False
        current_element: ElementType = None
        
        for line in lines:
            indent_level, clean_line = self._get_indentation_level(line)
            clean_content = self._clean_text(clean_line)
            element_type = self._get_element_type(line, clean_content, indent_level)
            print(f"Line: {line}, Indent Level: {indent_level}, Clean Content: '{clean_content}', Element Type: {element_type}")


            if clean_content != "" and not read_title:
                script.movie_title = clean_content
                read_title = True
                continue            

            if current_element is not None:
                if current_element.element_type == ElementType.DIALOGUE and clean_content == "":
                    if len(current_element.content) != 0:
                        current_element.content = Splitter.split(current_element.content[0])
                    yield current_element
                    current_element = None
                    continue
                # We just have a character name with no text, so change to "ACTION", keeping the character name
                # Have we changed the element type?
                elif current_element.element_type != element_type:
                    if current_element.element_type == ElementType.DIALOGUE:
                        current_element.content = Splitter.split(current_element.content[0])
                    yield current_element
                    current_element = None

            if clean_content == "":
                continue

            if not current_element:
                current_element = ScriptElement(
                    element_type,
                    [],
                    {'indentation': indent_level}
                )

            match current_element.element_type:
                case ElementType.ACTION:
                    if len(current_element.content) == 0:
                        current_element.content.append(clean_content)
                    else:
                        if current_element.content[0] != "":
                            current_element.content[0] += ' '
                        current_element.content[0] += clean_content
                    continue
                case ElementType.DIALOGUE:
                    if 'character' not in current_element.metadata:
                        current_element.metadata['character'] = clean_content
                    else:
                        if len(current_element.content) == 0:
                            current_element.content.append(clean_content)
                        else:
                            if current_element.content[0] != "":
                                current_element.content[0] += ' '
                            current_element.content[0] += clean_content
                    continue
                case ElementType.PARENTHETICAL:
                        if len(current_element.content) == 0:
                            current_element.content.append(clean_content)
                        else:
                            if current_element.content[0] != "":
                                current_element.content[0] += ' '
                            current_element.content[0] += clean_content
                case ElementType.SCENE_HEADING:
                    current_element.content.append(clean_content)
                    continue
                case ElementType.PARENTHETICAL:
                    current_element.content.append(clean_content)
                    continue
                case ElementType.TRANSITION:
                    current_element.content.append(clean_content)
                    continue
                case _:
                    continue  # Skip unrecognized types

    def parse_script(self, movie_title: str) -> Script:
        """Main method to parse a script by movie title."""
        script_url = f"{self.base_url}/scripts/{movie_title}.html"
            
        raw_text = self._extract_script_text(script_url)
        if not raw_text:
            logger.error(f"Could not extract text from {script_url}")
            return Script(title=movie_title, elements=[])
            
        script = Script(title=movie_title, elements=[])
        for element in self._parse_script_lines(raw_text):
            script.add_element(element)
        return script

# Example usage
if __name__ == "__main__":
    parser = ScriptParser()
    script = parser.parse_script("Big-Lebowski,-The")

    # save as json file
    with open('script_elements.json', 'w') as f:
        json.dump(asdict(script), f, indent=4, cls=CustomEncoder)