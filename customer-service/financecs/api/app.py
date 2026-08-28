"""
定义FastAPI实例（金融智能客服）
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from financecs.api.chat_router import router
from financecs.infrastructure.db_client import init_db_engine, dispose_engine
from financecs.infrastructure.http_client import init_http_client, disposed_http_client


async def lifespan(_: FastAPI):
    """fastapi 生命周期回调：启动初始化资源，关闭释放资源"""
    init_db_engine()
    init_http_client()

    yield

    await dispose_engine()
    await disposed_http_client()


app = FastAPI(title="金融智能客服系统", description="金融智能客服项目（电商客服项目改造）", lifespan=lifespan)

# 演示环境允许跨域（生产环境应收敛为白名单）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(router)
