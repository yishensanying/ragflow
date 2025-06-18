import '@js-preview/excel/lib/index.css';
import { Spin, Flex } from 'antd';
import FileError from '../file-error';
import { useFetchExcel } from '../hooks';

const Excel = ({ filePath }: { filePath: string }) => {
  const { status, loading, containerRef, error } = useFetchExcel(filePath);

  return (
    <div style={{ height: '100%', width: '100%', position: 'relative' }}>
      {loading && (
        <Flex justify="center" align="center" style={{ height: '100%', position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: '#fff' }}>
          <Spin size="large" />
        </Flex>
      )}
      {!loading && status === false && (
        <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <FileError>{error || 'Excel文件加载失败'}</FileError>
        </div>
      )}
    <div
      id="excel"
      ref={containerRef}
        style={{ 
          height: '100%', 
          width: '100%',
          visibility: loading ? 'hidden' : 'visible'
        }}
      />
    </div>
  );
};

export default Excel;
