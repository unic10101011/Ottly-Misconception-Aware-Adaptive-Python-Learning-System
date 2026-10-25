"""Answer optional lesson-guide questions through DeepSeek Flash."""
import httpx
from fastapi import HTTPException

from app.services import error_analysis


async def answer_question(story, question, history):
    if not error_analysis.DEEPSEEK_API_KEY:
        raise HTTPException(status_code=503, detail='DeepSeek API Key 尚未配置，请在后端配置 DEEPSEEK_API_KEY。你也可以直接继续。')
    # Only public teaching lines are context; quizzes and their answer keys stay local.
    context = '\n'.join(node['text'] for node in story['nodes'] if node['type'] == 'line')
    messages = [{'role': 'system', 'content': (
        '你是 Python 学习伙伴 Ottly。用简短、友善的中文解答初学者对当前关卡知识点的疑问，'
        '必要时给一个小例子；不要直接给出本关完整通关代码。只回答与 Python 学习相关的问题。'
        '以下是本关教学材料：\n'
        f"第 {story.get('levelNo', 1)} 关：{story['title']}\n知识点：{story['knowledge']}\n{context}"
    )}, *history, {'role': 'user', 'content': question}]
    try:
        async with httpx.AsyncClient(timeout=55) as client:
            response = await client.post(
                f'{error_analysis.DEEPSEEK_BASE_URL}/chat/completions',
                headers={'Authorization': f'Bearer {error_analysis.DEEPSEEK_API_KEY}'},
                json={'model': 'deepseek-flash', 'messages': messages, 'stream': False,
                      'thinking': {'type': 'disabled'}, 'max_tokens': 1024},
            )
            response.raise_for_status()
            choice = response.json()['choices'][0]
            answer = choice['message']['content']
            if choice.get('finish_reason') != 'stop' or not isinstance(answer, str) or not answer.strip():
                raise ValueError('Incomplete guide answer')
            return {'answer': answer.strip(), 'model': 'deepseek-flash'}
    except httpx.HTTPStatusError as error:
        message = {401: 'DeepSeek 密钥无效，请检查后端配置。', 402: 'DeepSeek 账户余额不足。',
                   429: 'DeepSeek 请求繁忙，请稍后重试。'}.get(error.response.status_code, 'DeepSeek 服务暂不可用，请稍后重试。')
        raise HTTPException(status_code=503, detail=message) from None
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail='解答超时，请重试或直接继续。') from None
    except (httpx.RequestError, ValueError, KeyError, IndexError, TypeError):
        raise HTTPException(status_code=502, detail='暂时未能获取完整解答，请重试或直接继续。') from None
