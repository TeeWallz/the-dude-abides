import re
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List, Optional, Iterator, Tuple
from enum import Enum, auto
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ElementType(Enum):
    ACTION = auto()
    CHARACTER = auto()
    LOCATION = auto()
    TRANSITION = auto()
    SCENE_HEADING = auto()
    PARENTHETICAL = auto()
    DIALOGUE = auto()

@dataclass
class ScriptElement:
    element_type: ElementType
    content: str
    metadata: Optional[dict] = None

    def __str__(self) -> str:
        return f"{self.element_type.name}: {self.content}"

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
    
    def _parse_script_lines(self, raw_text: str) -> Iterator[ScriptElement]:
        """Parse raw script text into structured elements using indentation."""
        lines = raw_text.split('\n')
        current_character = None
        current_dialogue = []
        in_dialogue = False
        
        for line in lines:
            indent_level, clean_line = self._get_indentation_level(line)
            clean_content = self._clean_text(clean_line)
            
            if not clean_content:
                continue
                
            # Scene headings (minimal indentation, often all caps)
            if indent_level <= 1 and clean_content.isupper() and len(clean_content.split()) > 2:
                if current_character and current_dialogue:
                    yield ScriptElement(
                        ElementType.DIALOGUE,
                        ' '.join(current_dialogue),
                        {'character': current_character}
                    )
                    current_dialogue = []
                current_character = None
                yield ScriptElement(ElementType.SCENE_HEADING, clean_content)
                
            # Character names (triple indented)
            elif indent_level >= 3 and len(clean_content.split()) <= 3:
                if current_character and current_dialogue:
                    yield ScriptElement(
                        ElementType.DIALOGUE,
                        ' '.join(current_dialogue),
                        {'character': current_character}
                    )
                current_character = clean_content.upper()
                current_dialogue = []
                in_dialogue = True
                
            # Dialogue (following character name)
            elif in_dialogue and indent_level >= 2:
                current_dialogue.append(clean_content)
                
            # Parentheticals (wrylies)
            elif clean_content.startswith('(') and clean_content.endswith(')'):
                yield ScriptElement(
                    ElementType.PARENTHETICAL,
                    clean_content[1:-1],
                    {'character': current_character}
                )
                
            # Actions (everything else)
            else:
                if current_character and current_dialogue:
                    yield ScriptElement(
                        ElementType.DIALOGUE,
                        ' '.join(current_dialogue),
                        {'character': current_character}
                    )
                    current_dialogue = []
                current_character = None
                in_dialogue = False
                yield ScriptElement(ElementType.ACTION, clean_content)
                
        # Yield any remaining dialogue
        if current_character and current_dialogue:
            yield ScriptElement(
                ElementType.DIALOGUE,
                ' '.join(current_dialogue),
                {'character': current_character}
            )

    def parse_script(self, movie_title: str) -> List[ScriptElement]:
        """Main method to parse a script by movie title."""
        formatted_title = movie_title.replace(' ', '-').replace(',', '').title()
        script_url = f"{self.base_url}/scripts/{formatted_title}.html"
            
        raw_text = self._extract_script_text(script_url)
        if not raw_text:
            logger.error(f"Could not extract text from {script_url}")
            return []
            
        return list(self._parse_script_lines(raw_text))

# Example usage
if __name__ == "__main__":
    parser = ScriptParser()
    script_elements = parser.parse_script("Big Lebowski, The")
    
    for element in script_elements:
        if element.element_type in (ElementType.CHARACTER, ElementType.DIALOGUE, ElementType.SCENE_HEADING):
            print(element)