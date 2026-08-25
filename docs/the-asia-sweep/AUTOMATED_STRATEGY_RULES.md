# BỘ QUY TẮC THUẬT TOÁN ĐẶC TẢ TỰ ĐỘNG: ASIA RANGE SWEEP & JUDAS SWING
Dành cho việc lập trình Bot tự động hóa (Automated Trading) trên EUR/USD & GBP/USD.

## 1. Bản chất Vi cấu trúc & Bằng chứng định lượng
- Phiên Á là vùng tích lũy thanh khoản mỏng (Thin Liquidity).
- Stop Loss tập trung ở 2 đầu (Buy-side Liquidity và Sell-side Liquidity).
- Phiên London mở cửa tạo Judas Swing quét thanh khoản để ngân hàng gom/xả lệnh lớn.

## 2. Quy tắc Vào lệnh (Trading Strategy Rules)
- HTF Filter (H1): Chỉ giao dịch thuận xu hướng chính.

## 3. Các Setup Xấu Cần Loại Bỏ (Bad Setups & Edge Filters)
- Tin tức mạnh (High-Impact News: CPI, NFP, Lãi suất): Tắt bot trước 30p, mở sau 30p.
- Asian Range quá rộng (> 40 pips EUR, > 50 pips GBP): Bỏ qua.
- Nến quét đóng nến thân đặc (Full Body Breakout): Bỏ qua.
- Quét ngược xu hướng H1: Bỏ qua.
- Tín hiệu xuất hiện muộn sau 12:00 UTC: Bỏ qua.
