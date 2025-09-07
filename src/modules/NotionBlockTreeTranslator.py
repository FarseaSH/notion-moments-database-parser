from dataclasses import dataclass
from src.modules.notion_modules.NotionBlockTree import NotionBlockTree


@dataclass
class NotionBlockTreeTranlatedResult:
    md_text: str
    images: list[str]


class NotionBlockTreeTranslator:
    _LIST_ITEM = {"numbered_list_item", "bulleted_list_item"}  # 列表的解析需要特殊处理

    def __init__(self, block_tree: NotionBlockTree) -> None:
        self.block_tree = block_tree
        self.block_to_parse_queue: list[NotionBlockTree] = []
        self.md_paragraphs: list[str] = []
        self.images = []


    def translate(self) -> 'NotionBlockTreeTranlatedResult':
        self.block_to_parse_queue.append(self.block_tree)
        while self.block_to_parse_queue:
            tree_node = self.block_to_parse_queue.pop(0)
            notion_block_dict = tree_node.val

            if notion_block_dict is None:
                pass
            elif notion_block_dict['type'] in self._LIST_ITEM:
                self._parse_list_item(tree_node=tree_node)
            elif notion_block_dict['type'] == "paragraph": 
                self._parse_paragraph(notion_block_dict=notion_block_dict)
            elif notion_block_dict['type'] == "image": 
                self._parse_image(notion_block_dict=notion_block_dict)
            elif notion_block_dict['type'] == "code":
                self._parse_code(notion_block_dict=notion_block_dict)
            elif notion_block_dict['type'] == "quote":
                self._parse_quote(notion_block_dict=notion_block_dict)


            if notion_block_dict is not None and notion_block_dict['type'] in self._LIST_ITEM: continue

            if tree_node.next_block is not None: self.block_to_parse_queue.insert(0, tree_node.next_block)
            if tree_node.children_block is not None: self.block_to_parse_queue.insert(0, tree_node.children_block)


        return NotionBlockTreeTranlatedResult(md_text="\n\n".join(self.md_paragraphs), images=self.images)


    def _parse_list_item(self, tree_node: 'NotionBlockTree'):
        result: 'list[str]' = []

        def dfs(node: 'NotionBlockTree', index_level: int, numbered_list_number: int):
            """
            只解析 {"numbered_list_item", "bulleted_list_item"}        

            index_level: 从 0 开始
            numbered_list_number: 从 1 开始，记录序号列表当前的序号
            """

            notion_block_dict = node.val
            if notion_block_dict is None or notion_block_dict['type'] not in self._LIST_ITEM:
                return node

            if notion_block_dict['type'] == 'numbered_list_item':
                _content = self._extract_rich_text(notion_block_dict['numbered_list_item']['rich_text'])
                result.append(" " * 4 * index_level + f"{numbered_list_number}. {_content}")
                numbered_list_number += 1
            else:  # bulleted_list_item
                _content = self._extract_rich_text(notion_block_dict['bulleted_list_item']['rich_text'])
                result.append(" " * 4 * index_level + f"- {_content}")

            if node.children_block is not None:
                dfs(node.children_block, index_level + 1, 1)

            if node.next_block is not None:
                next_node = dfs(node.next_block, index_level, numbered_list_number)
            else:
                next_node = None

            return next_node

        next_node = dfs(tree_node, 0, 1)
        self.md_paragraphs.append("\n".join(result))
        if next_node is not None: self.block_to_parse_queue.insert(0, next_node)


    def _parse_paragraph(self, notion_block_dict: dict):
        self.md_paragraphs.append(
            self._extract_rich_text(notion_block_dict['paragraph']['rich_text'])
        )


    def _parse_image(self, notion_block_dict: dict):
        url = notion_block_dict['image']['file']['url'] if 'file' in notion_block_dict['image'] \
                else notion_block_dict['image']['external']['url']
        self.images.append((url))
    

    def _parse_code(self, notion_block_dict: dict):
        code = notion_block_dict['code']
        language = code.get("language", "")
        code_text = "".join(rich_text_part['plain_text'] for rich_text_part in code['rich_text'])
        
        self.md_paragraphs.append(f"""```{language}\n{code_text}\n```""")


    def _parse_quote(self, notion_block_dict: dict):
        rich_text_extracted = self._extract_rich_text(notion_block_dict['quote']['rich_text'])
        quote_result = "\n>\n".join("> " + line for line in rich_text_extracted.split('\n'))
        self.md_paragraphs.append(quote_result)


    @staticmethod
    def _extract_rich_text(rich_text: 'list[dict]', only_plain_text=False) -> str:
        result: 'list[str]' = []
        for rich_text_part in rich_text:
            text = rich_text_part['plain_text']

            if only_plain_text:
                result.append(text)
                continue

            if rich_text_part['annotations']['bold']: text = f"**{text}**"
            if rich_text_part['annotations']['italic']: text = f"*{text}*"
            if rich_text_part['annotations']['strikethrough']: text = f"~~{text}~~"
            if rich_text_part['annotations']['code']: text = f"`{text}`"
            if 'href' in rich_text_part and rich_text_part['href']:
                text = f"[{text}]({rich_text_part['href']})"

            result.append(text)
        
        return "".join(result)
