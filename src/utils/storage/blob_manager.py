#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Azure Blob Storage管理器
负责处理JSON文件的上传、下载和管理功能
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient, ContentSettings
from azure.core.exceptions import AzureError, ResourceNotFoundError

from src.core import get_logger, settings

logger = get_logger(__name__)


class BlobStorageManager:
    """Azure Blob Storage管理器"""
    
    def __init__(self, connection_string: Optional[str] = None, container_name: Optional[str] = None):
        """
        初始化Blob Storage管理器
        
        Args:
            connection_string: Azure Storage连接字符串，如果为None则从环境变量读取
            container_name: 容器名称，如果为None则从环境变量读取
        """
        self.connection_string = connection_string or settings.AZURE_STORAGE_CONNECTION_STRING
        self.container_name = container_name or settings.AZURE_BLOB_CONTAINER_NAME
        
        if not self.connection_string:
            raise ValueError("Azure Storage连接字符串未配置，请在.env文件中设置AZURE_STORAGE_CONNECTION_STRING")
        
        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
            self.container_client = self.blob_service_client.get_container_client(self.container_name)
            
            # 确保容器存在
            self._ensure_container_exists()
            
            logger.info(f"✅ Azure Blob Storage管理器初始化成功，容器: {self.container_name}")
            
        except Exception as e:
            logger.error(f"❌ Azure Blob Storage管理器初始化失败: {e}")
            raise
    
    def _ensure_container_exists(self):
        """确保容器存在，如果不存在则创建"""
        try:
            # 尝试获取容器属性
            self.container_client.get_container_properties()
            logger.debug(f"容器 {self.container_name} 已存在")
        except ResourceNotFoundError:
            # 容器不存在，创建它
            try:
                self.container_client.create_container()
                logger.info(f"✅ 已创建容器: {self.container_name}")
            except Exception as e:
                logger.error(f"❌ 创建容器失败: {e}")
                raise
    
    def upload_json_file(self, local_file_path: str, blob_name: Optional[str] = None, 
                        product_category: Optional[str] = None) -> str:
        """
        上传JSON文件到Blob Storage
        
        Args:
            local_file_path: 本地文件路径
            blob_name: Blob名称，如果为None则自动生成
            product_category: 产品分类，用于组织文件结构
            
        Returns:
            str: 上传后的Blob URL
        """
        local_path = Path(local_file_path)
        
        if not local_path.exists():
            raise FileNotFoundError(f"本地文件不存在: {local_file_path}")
        
        # 生成Blob名称
        if not blob_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if product_category:
                blob_name = f"{product_category}/{local_path.name}"
            else:
                blob_name = f"exports/{timestamp}/{local_path.name}"
        
        try:
            # 读取文件内容
            with open(local_path, 'rb') as data:
                blob_client = self.container_client.get_blob_client(blob_name)
                
                # 设置内容类型和元数据
                content_settings = ContentSettings(
                    content_type='application/json',
                    content_encoding='utf-8'
                )
                
                metadata = {
                    'upload_time': datetime.utcnow().isoformat(),
                    'original_filename': local_path.name,
                    'file_size': str(local_path.stat().st_size)
                }
                
                if product_category:
                    metadata['product_category'] = product_category
                
                # 上传文件
                blob_client.upload_blob(
                    data, 
                    overwrite=True,
                    content_settings=content_settings,
                    metadata=metadata
                )
                
                blob_url = blob_client.url
                logger.info(f"✅ 文件上传成功: {local_path.name} -> {blob_name}")
                logger.debug(f"Blob URL: {blob_url}")
                
                return blob_url
                
        except Exception as e:
            logger.error(f"❌ 文件上传失败 {local_path.name}: {e}")
            raise
    
    def upload_directory(self, directory_path: str, blob_prefix: Optional[str] = None) -> List[Dict[str, str]]:
        """
        上传目录中的所有JSON文件
        
        Args:
            directory_path: 目录路径
            blob_prefix: Blob名称前缀
            
        Returns:
            List[Dict[str, str]]: 上传结果列表，包含本地路径和Blob URL
        """
        directory = Path(directory_path)
        
        if not directory.exists() or not directory.is_dir():
            raise ValueError(f"目录不存在或不是有效目录: {directory_path}")
        
        results = []
        json_files = list(directory.rglob("*.json"))
        
        if not json_files:
            logger.warning(f"目录中没有找到JSON文件: {directory_path}")
            return results
        
        logger.info(f"🔄 开始上传目录中的 {len(json_files)} 个JSON文件...")
        
        for json_file in json_files:
            try:
                # 计算相对路径作为产品分类
                relative_path = json_file.relative_to(directory)
                product_category = relative_path.parent.name if relative_path.parent.name != '.' else None
                
                # 生成Blob名称
                if blob_prefix:
                    blob_name = f"{blob_prefix}/{relative_path}"
                else:
                    blob_name = str(relative_path).replace('\\', '/')
                
                blob_url = self.upload_json_file(
                    str(json_file), 
                    blob_name=blob_name,
                    product_category=product_category
                )
                
                results.append({
                    'local_path': str(json_file),
                    'blob_name': blob_name,
                    'blob_url': blob_url,
                    'product_category': product_category
                })
                
            except Exception as e:
                logger.error(f"❌ 上传文件失败 {json_file}: {e}")
                results.append({
                    'local_path': str(json_file),
                    'blob_name': None,
                    'blob_url': None,
                    'error': str(e)
                })
        
        successful_uploads = len([r for r in results if r.get('blob_url')])
        logger.info(f"✅ 目录上传完成: {successful_uploads}/{len(json_files)} 个文件成功上传")
        
        return results
    
    def list_blobs(self, name_starts_with: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出容器中的Blob文件
        
        Args:
            name_starts_with: 名称前缀过滤
            
        Returns:
            List[Dict[str, Any]]: Blob信息列表
        """
        try:
            blobs = []
            blob_list = self.container_client.list_blobs(name_starts_with=name_starts_with)
            
            for blob in blob_list:
                blob_info = {
                    'name': blob.name,
                    'size': blob.size,
                    'last_modified': blob.last_modified,
                    'content_type': blob.content_settings.content_type if blob.content_settings else None,
                    'metadata': blob.metadata or {}
                }
                blobs.append(blob_info)
            
            logger.debug(f"列出 {len(blobs)} 个Blob文件")
            return blobs
            
        except Exception as e:
            logger.error(f"❌ 列出Blob文件失败: {e}")
            raise
    
    def delete_blob(self, blob_name: str) -> bool:
        """
        删除指定的Blob文件
        
        Args:
            blob_name: Blob名称
            
        Returns:
            bool: 删除是否成功
        """
        try:
            blob_client = self.container_client.get_blob_client(blob_name)
            blob_client.delete_blob()
            logger.info(f"✅ 已删除Blob: {blob_name}")
            return True
            
        except ResourceNotFoundError:
            logger.warning(f"⚠️ Blob不存在: {blob_name}")
            return False
        except Exception as e:
            logger.error(f"❌ 删除Blob失败 {blob_name}: {e}")
            return False
    
    def generate_sas_url(self, blob_name: str, expiry_hours: int = 24) -> str:
        """
        生成Blob的SAS URL，用于临时访问
        
        Args:
            blob_name: Blob名称
            expiry_hours: 过期时间（小时）
            
        Returns:
            str: SAS URL
        """
        try:
            from azure.storage.blob import generate_blob_sas, BlobSasPermissions
            
            # 生成SAS token
            sas_token = generate_blob_sas(
                account_name=self.blob_service_client.account_name,
                container_name=self.container_name,
                blob_name=blob_name,
                account_key=self._get_account_key(),
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=expiry_hours)
            )
            
            blob_client = self.container_client.get_blob_client(blob_name)
            sas_url = f"{blob_client.url}?{sas_token}"
            
            logger.debug(f"生成SAS URL: {blob_name} (有效期: {expiry_hours}小时)")
            return sas_url
            
        except Exception as e:
            logger.error(f"❌ 生成SAS URL失败 {blob_name}: {e}")
            raise
    
    def _get_account_key(self) -> str:
        """从连接字符串中提取账户密钥"""
        try:
            # 解析连接字符串
            parts = self.connection_string.split(';')
            for part in parts:
                if part.startswith('AccountKey='):
                    return part.split('=', 1)[1]
            raise ValueError("连接字符串中未找到AccountKey")
        except Exception as e:
            logger.error(f"❌ 提取账户密钥失败: {e}")
            raise
    
    def get_blob_info(self, blob_name: str) -> Optional[Dict[str, Any]]:
        """
        获取指定Blob的详细信息
        
        Args:
            blob_name: Blob名称
            
        Returns:
            Optional[Dict[str, Any]]: Blob信息，如果不存在返回None
        """
        try:
            blob_client = self.container_client.get_blob_client(blob_name)
            properties = blob_client.get_blob_properties()
            
            return {
                'name': blob_name,
                'size': properties.size,
                'last_modified': properties.last_modified,
                'content_type': properties.content_settings.content_type,
                'metadata': properties.metadata or {},
                'url': blob_client.url
            }
            
        except ResourceNotFoundError:
            logger.debug(f"Blob不存在: {blob_name}")
            return None
        except Exception as e:
            logger.error(f"❌ 获取Blob信息失败 {blob_name}: {e}")
            raise
