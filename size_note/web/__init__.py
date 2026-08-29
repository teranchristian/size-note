from fastapi.templating import Jinja2Templates

from size_note.config import get_settings

templates = Jinja2Templates(directory=get_settings().package_dir / "templates")
