# 章程验证脚本

用于验证项目是否符合 `.specify/memory/constitution.md` 中定义的章程原则。

## 脚本列表

- `check_file_length.py` - 验证所有Python源文件不超过4000行限制
- `check_temp_files.py` - 检查仓库中是否存在不应提交的临时文件
- `check_directory_structure.py` - 验证项目目录结构是否符合规范
- `run_all_checks.py` - 运行所有验证检查

## 使用方法

```bash
# 运行所有检查
python scripts/validation/run_all_checks.py

# 或单独运行某个检查
python scripts/validation/check_file_length.py
```
