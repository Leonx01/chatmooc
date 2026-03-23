1. User（用户表）
字段名 数据类型 约束 说明
uid INT PRIMARY KEY, AUTO_INCREMENT 用户唯一ID
uname VARCHAR(50) NOT NULL 用户名
created_at DATETIME NOT NULL, DEFAULT CURRENT_TIMESTAMP 账号创建时间
updated_at DATETIME NOT NULL, DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP 信息更新时间

2. Resource（学习资源表）
字段名 数据类型 约束 说明
rid CHAR(36) PRIMARY KEY 资源唯一ID（UUID）
uid CHAR(36) NOT NULL, FOREIGN KEY REFERENCES User(uid) 所属用户ID
url VARCHAR(256) NOT NULL 资源文件地址（对外可访问）
storage_provider VARCHAR(20) NULL 存储类型（local/oss）
storage_key VARCHAR(512) NULL 存储对象 Key（本地或 OSS）
rname VARCHAR(100) NOT NULL 资源名称
rtype VARCHAR(20) NOT NULL 资源类型（如文档/视频/音频）
content TEXT NULL 资源原始文本内容
summary TEXT NULL 摘要待生成
keywords JSON NULL 几个关键词
created_at DATETIME NOT NULL, DEFAULT CURRENT_TIMESTAMP 资源创建时间
updated_at DATETIME NOT NULL, DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP 资源更新时间

3. Session（学习会话表）
字段名 数据类型 约束 说明
sid INT PRIMARY KEY, AUTO_INCREMENT 会话唯一ID
uid INT NOT NULL, FOREIGN KEY REFERENCES User(uid) 所属用户ID
created_at DATETIME NOT NULL, DEFAULT CURRENT_TIMESTAMP 会话开始时间

4. SessionResource（会话-资源关联表，多对多中间表）
字段名 数据类型 约束 说明
sid INT NOT NULL, FOREIGN KEY REFERENCES Session(sid), PRIMARY KEY 会话ID
rid INT NOT NULL, FOREIGN KEY REFERENCES Resource(rid), PRIMARY KEY 资源ID
added_at DATETIME NOT NULL, DEFAULT CURRENT_TIMESTAMP 资源加入会话的时间

4. Path
pid UUID
description TEXT NULL 会话描述


5. Unit（学习单元表）
字段名 数据类型 约束 说明
unit_id INT PRIMARY KEY, AUTO_INCREMENT 学习单元唯一ID
pid INT NOT NULL, FOREIGN KEY REFERENCES Path(pid) 所属路径ID
uid INT NOT NULL, FOREIGN KEY REFERENCES User(uid) 所属用户ID
goal VARCHAR(200) NOT NULL 单元学习目标
guide TEXT NOT NULL 单元学习指导/大纲
created_at DATETIME NOT NULL, DEFAULT CURRENT_TIMESTAMP 单元创建时间
completed_at DATETIME NULL 单元完成时间

6. FlashCard（闪卡表）
字段名 数据类型 约束 说明
fcid INT PRIMARY KEY, AUTO_INCREMENT 闪卡唯一ID
unit_id INT NOT NULL, FOREIGN KEY REFERENCES Unit(unit_id) 所属学习单元ID
uid INT NOT NULL, FOREIGN KEY REFERENCES User(uid) 所属用户ID
question TEXT NOT NULL 闪卡问题/正面内容
answer TEXT NOT NULL 闪卡答案/反面内容
review_count INT NOT NULL, DEFAULT 0 复习次数
last_reviewed_at DATETIME NULL 最后复习时间
created_at DATETIME NOT NULL, DEFAULT CURRENT_TIMESTAMP 闪卡创建时间

7. Exercise（练习题表）
字段名 数据类型 约束 说明
eid INT PRIMARY KEY, AUTO_INCREMENT 练习题唯一ID
unit_id INT NOT NULL, FOREIGN KEY REFERENCES Unit(unit_id) 所属学习单元ID
uid INT NOT NULL, FOREIGN KEY REFERENCES User(uid) 所属用户ID
question TEXT NOT NULL 题目内容
options JSON NULL 选择题选项（JSON格式存储）
correct_answer TEXT NOT NULL 正确选项
explanation TEXT NULL 答案解析
created_at DATETIME NOT NULL, DEFAULT CURRENT_TIMESTAMP 题目创建时间

8. MilvusVector
字段名 数据类型 约束 说明
rid INT PRIMARY KEY, FOREIGN KEY REFERENCES Resource(rid) 关联资源ID（与Resource表一一对应）
uid INT NOT NULL, FOREIGN KEY REFERENCES User(uid) 所属用户ID
content TEXT NOT NULL 向量化的文本片段/内容
chunk_num INT NOT NULL 第几个Chunk
vector VECTOR(768) NOT NULL 内容的向量表示（维度根据模型调整）
created_at DATETIME NOT NULL, DEFAULT CURRENT_TIMESTAMP 向量生成时间
-- 9) MilvusVector (milvus_vectors)
-- schema.md has "vector VECTOR(768)" and "rid is PK" but also says one Resource splits into many chunks.
-- MySQL community doesn't have a stable VECTOR(768) type; keep embedding bytes as BLOB (optional),
-- and model the 1:N chunks via UNIQUE(rid, chunk_num).
CREATE TABLE milvus_vectors (
  id CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT '向量记录ID(UUID)',
  rid CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT '关联资源ID(UUID)',
  uid CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT '所属用户ID(UUID)',
  content TEXT NOT NULL COMMENT '向量化的文本片段/内容',
  chunk_num INT UNSIGNED NOT NULL COMMENT '第几个Chunk',
  vector BLOB NULL COMMENT '向量字节(可选，通常向量存Milvus，这里存元数据/回填)',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '向量生成时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_milvus_vectors_rid_chunk (rid, chunk_num),
  KEY idx_milvus_vectors_uid_created (uid, created_at),
  CONSTRAINT fk_milvus_vectors_rid
    FOREIGN KEY (rid) REFERENCES resources(rid)
    ON DELETE CASCADE,
  CONSTRAINT fk_milvus_vectors_uid
    FOREIGN KEY (uid) REFERENCES users(uid)
    ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;
关系总结

• User 是根节点，拥有 Resource、Session、Unit、FlashCard、Practice 所有数据。

• Session 与 Resource 是多对多关系，通过 SessionResource 关联。

• Unit 从属于 Session，是生成 FlashCard 和 Practice 的核心单元。

 一个Resource 可能被切分为多个chunk存入Milvus
