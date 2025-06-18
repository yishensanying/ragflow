import { Authorization } from '@/constants/authorization';
import { getAuthorization } from '@/utils/authorization-util';
import jsPreviewExcel from '@js-preview/excel';
import axios from 'axios';
import mammoth from 'mammoth';
import { useCallback, useEffect, useRef, useState } from 'react';

// 移除了useCatchError函数，因为它会导致重复请求

export const useFetchDocument = () => {
  const fetchDocument = useCallback(async (api: string) => {
    const ret = await axios.get(api, {
      headers: {
        [Authorization]: getAuthorization(),
      },
      responseType: 'arraybuffer',
    });
    return ret;
  }, []);

  return { fetchDocument };
};

export const useFetchExcel = (filePath: string) => {
  const [status, setStatus] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const { fetchDocument } = useFetchDocument();
  const containerRef = useRef<HTMLDivElement>(null);

  const fetchDocumentAsync = useCallback(async () => {
    try {
      setLoading(true);
      setError('');

      if (!containerRef.current) {
        console.error('Excel container not found');
        setError('Excel container not found');
        setStatus(false);
        setLoading(false);
        return;
      }

      // 获取数据
      const jsonFile = await fetchDocument(filePath);

      // 等待容器准备好
      await new Promise(resolve => {
        const checkContainer = () => {
          if (containerRef.current && containerRef.current.offsetHeight > 0) {
            resolve(undefined);
          } else {
            setTimeout(checkContainer, 50);
          }
        };
        checkContainer();
      });

      // 清空容器并设置基础样式
    if (containerRef.current) {
        containerRef.current.innerHTML = '';
        containerRef.current.style.width = '100%';
        containerRef.current.style.height = '100%';
        containerRef.current.style.overflow = 'auto';
    }

      // 初始化Excel预览器
      const myExcelPreviewer = jsPreviewExcel.init(containerRef.current);
      if (!myExcelPreviewer) {
        console.error('Failed to initialize Excel previewer');
        setError('Failed to initialize Excel previewer');
        setStatus(false);
        setLoading(false);
        return;
      }

      // 预览Excel文件
    myExcelPreviewer
        .preview(jsonFile.data)
      .then(() => {
          console.log('Excel preview succeed');
        setStatus(true);
          setLoading(false);
      })
      .catch((e) => {
          console.warn('Excel preview failed', e);
          setError(e?.message || 'Excel preview failed');
          if (myExcelPreviewer && typeof myExcelPreviewer.destroy === 'function') {
        myExcelPreviewer.destroy();
          }
        setStatus(false);
          setLoading(false);
      });
    } catch (err: any) {
      console.error('Excel fetch error:', err);
      setError(err?.message || 'Excel fetch error');
      setStatus(false);
      setLoading(false);
    }
  }, [filePath, fetchDocument]);

  useEffect(() => {
    fetchDocumentAsync();
  }, [fetchDocumentAsync]);

  return { status, loading, containerRef, error };
};

export const useFetchDocx = (filePath: string) => {
  const [succeed, setSucceed] = useState(true);
  const [error, setError] = useState<string>();
  const { fetchDocument } = useFetchDocument();
  const containerRef = useRef<HTMLDivElement>(null);

  const fetchDocumentAsync = useCallback(async () => {
    try {
      const jsonFile = await fetchDocument(filePath);
      mammoth
        .convertToHtml(
          { arrayBuffer: jsonFile.data },
          { includeDefaultStyleMap: true },
        )
        .then((result) => {
          setSucceed(true);
          const docEl = document.createElement('div');
          docEl.className = 'document-container';
          docEl.innerHTML = result.value;
          const container = containerRef.current;
          if (container) {
            container.innerHTML = docEl.outerHTML;
          }
        })
        .catch(() => {
          setSucceed(false);
        });
    } catch (error: any) {
      setError(error.toString());
    }
  }, [filePath, fetchDocument]);

  useEffect(() => {
    fetchDocumentAsync();
  }, [fetchDocumentAsync]);

  return { succeed, containerRef, error };
};
