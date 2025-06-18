import { Spin } from 'antd';
import { useEffect, useState } from 'react';
import { Authorization } from '@/constants/authorization';
import { getAuthorization } from '@/utils/authorization-util';
import FileError from '../file-error';
import styles from './index.less';

interface TextProps {
  filePath: string;
}

const Text = ({ filePath }: TextProps) => {
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    const fetchTextContent = async () => {
      try {
        setLoading(true);
        const response = await fetch(filePath, {
          headers: {
            [Authorization]: getAuthorization(),
          },
        });
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const text = await response.text();
        setContent(text);
        setError('');
      } catch (err: any) {
        console.error('Failed to load text file:', err);
        setError(err.message || 'Failed to load text file');
      } finally {
        setLoading(false);
      }
    };

    if (filePath) {
      fetchTextContent();
    }
  }, [filePath]);

  if (loading) {
    return (
      <div className={styles.textViewerWrapper}>
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return <FileError>{error}</FileError>;
  }

  return (
    <div className={styles.textViewerWrapper}>
      <pre className={styles.textContent}>
        {content}
      </pre>
    </div>
  );
};

export default Text; 