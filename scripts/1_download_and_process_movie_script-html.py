import re
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List, Optional, Iterator, Tuple
from enum import Enum, auto
import logging
# import sentence-splitter

from sentence_splitter import SentenceSplitter

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
    metadata: Optional[dict] = None
    content: str | List[str]

    def __str__(self) -> str:
        return f"{self.element_type.name}: {self.content}"

film_title = ""
Splitter = SentenceSplitter(language='en')

class ScriptParser:
    """A robust parser for IMSDB script pages that handles tab-based formatting."""
    
    def __init__(self):
        self.base_url = "https://imsdb.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
    def _clean_text(self, text: str, include_tabs: bool = False) -> str:
        """Clean and normalize text while preserving meaningful whitespace."""
        text = text.replace('\r', '').replace('\n', '')
        if include_tabs:
            text = text.replace('\t', '')
        text = re.sub(r' +', ' ', text)  # Collapse multiple spaces
        return text.strip()
    
    def _get_indentation_level(self, line: str) -> Tuple[int, str]:
        """Determine the indentation level and clean the line."""
        if not line.text:
            return 0, ""
            
        # Count tabs and leading spaces
        tabs = 0
        spaces = 0
        for char in line.text:
            if char == '\t':
                tabs += 1
            elif char == ' ':
                spaces += 1
            else:
                break
                
        # Convert spaces to tab equivalents (assuming 4 spaces = 1 tab)
        total_indent = tabs + (spaces // 4)
        cleaned_line = line.text[tabs + spaces:]
        
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
                
            return script_parent.find("pre").find("pre")
        except Exception as e:
            logger.error(f"Error extracting script text: {e}")
            return None
        

    def split_sentences(self, text: str) -> List[str]:
        """Split text into sentences using the sentence-splitter library."""
        return Splitter.split(text)
        
    def _parse_script_lines(self, raw_text: str) -> Iterator[ScriptElement]:
        """Parse raw script text into structured elements using indentation."""
        lines = raw_text
        current_character = None
        current_dialogue = []
        in_dialogue = False
        has_read_title = False
        
        for line in lines:
            indent_level, clean_line = self._get_indentation_level(line)
            clean_content = self._clean_text(clean_line)
            
            if not clean_content:
                continue
            if not has_read_title:
                film_title = clean_content
                has_read_title = True
                continue
            # Scene headings (minimal indentation, often all caps)
            elif indent_level <= 1 and clean_content.isupper() and len(clean_content.split()) > 2:
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
                        current_dialogue,
                        {'character': current_character}
                    )
                current_character = clean_content.upper()
                current_dialogue = []
                in_dialogue = True
                
            # Dialogue (following character name)
            elif in_dialogue and indent_level >= 2:
                lines_of_dialogue = self.split_sentences(clean_content)
                clean_lines_of_dialogue = [self._clean_text(line, True) for line in lines_of_dialogue]
                # append to current dialogue
                if clean_lines_of_dialogue:
                    current_dialogue.extend(clean_lines_of_dialogue)               
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
        script_url = f"{self.base_url}/scripts/{movie_title}.html"
            
        script = self._extract_script_text(script_url)
        if not script:
            logger.error(f"Could not extract text from {script_url}")
            return []
            
        return list(self._parse_script_lines(script))

# Example usage
if __name__ == "__main__":
    parser = ScriptParser()
    script_elements = parser.parse_script("Big-Lebowski,-The")
    
    for element in script_elements:
        if element.element_type in (ElementType.CHARACTER, ElementType.DIALOGUE, ElementType.SCENE_HEADING):
            print(element)