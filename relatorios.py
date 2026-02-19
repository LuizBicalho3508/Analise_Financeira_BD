import streamlit as st
import pandas as pd
import io
from fpdf import FPDF
import datetime
import tempfile
import os

# --- GERADOR DE PDF PRINCIPAL ---
class PDFReport(FPDF):
    def __init__(self, titulo, usuario):
        super().__init__()
        self.titulo = titulo
        self.usuario = usuario
        self.data_emissao = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    def header(self):
        try:
            self.image('logo-brasil-digital.png', 10, 8, 33)
        except: pass
        
        self.set_font('Arial', 'B', 15)
        self.cell(80)
        self.cell(30, 10, self.titulo, 0, 0, 'C')
        self.ln(20)
        
        self.set_draw_color(0, 166, 81) # Verde Brasil Digital
        self.set_line_width(1)
        self.line(10, 25, 200, 25)
        
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Gerado por: {self.usuario} | Em: {self.data_emissao}', 0, 1, 'R')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

# --- PDF: DASHBOARD ---
def gerar_pdf_analitico(df, metrics, figures, user_name):
    pdf = PDFReport("Relatório Financeiro", user_name)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(0, 39, 118) # Azul Brasil Digital
    pdf.cell(0, 10, 'Resumo Geral', 0, 1)
    pdf.set_text_color(0, 0, 0) 
    
    pdf.set_font('Arial', '', 10)
    col_w = 45
    for key, value in metrics.items():
        pdf.cell(col_w, 10, f"{key}", 1, 0, 'C')
    pdf.ln()
    pdf.set_font('Arial', 'B', 11)
    for key, value in metrics.items():
        pdf.cell(col_w, 10, f"{value}", 1, 0, 'C')
    pdf.ln(15)

    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(0, 39, 118)
    pdf.cell(0, 10, 'Análise Gráfica', 0, 1)
    pdf.set_text_color(0, 0, 0)
    
    try:
        with tempfile.TemporaryDirectory() as tmpdirname:
            for i, fig in enumerate(figures):
                if fig:
                    fig.update_layout(template="plotly_white", paper_bgcolor="white", plot_bgcolor="white", font=dict(color="black"))
                    img_path = os.path.join(tmpdirname, f"chart_dash_{i}.png")
                    fig.write_image(img_path, width=800, height=450, scale=2)
                    
                    if pdf.get_y() > 200:
                        pdf.add_page()
                    
                    pdf.image(img_path, x=10, w=190)
                    pdf.ln(5)
    except Exception as e:
        pdf.set_font('Arial', 'I', 10)
        pdf.set_text_color(255, 0, 0)
        pdf.cell(0, 10, f"Erro ao gerar gráficos: {e}", 0, 1)
        pdf.set_text_color(0, 0, 0)

    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(0, 39, 118)
    pdf.cell(0, 10, 'Detalhamento (Top 50 Registros)', 0, 1)
    pdf.set_text_color(0, 0, 0)
    
    pdf.set_font('Arial', 'B', 7)
    cols = ['Nome', 'Cargo', 'Empresa', 'Valor (R$)']
    w_cols = [60, 50, 50, 30]
    
    for i, c in enumerate(cols):
        pdf.cell(w_cols[i], 7, c, 1, 0, 'C')
    pdf.ln()
    
    pdf.set_font('Arial', '', 7)
    df_top = df.head(50)
    
    for _, row in df_top.iterrows():
        try:
            pdf.cell(w_cols[0], 6, str(row['Nome'])[:35], 1)
            pdf.cell(w_cols[1], 6, str(row['Cargo'])[:30], 1)
            pdf.cell(w_cols[2], 6, str(row['Empresa'])[:25], 1)
            pdf.cell(w_cols[3], 6, f"{row['Valor (R$)']:,.2f}", 1, 0, 'R')
            pdf.ln()
        except: pass

    return pdf.output(dest='S').encode('latin-1')

# --- PDF: CENÁRIOS / SIMULADOR ---
def gerar_pdf_cenarios(df, metrics, figures, user_name):
    pdf = PDFReport("Simulação de Cenários", user_name)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(0, 39, 118) 
    pdf.cell(0, 10, 'Impacto Projetado', 0, 1)
    pdf.set_text_color(0, 0, 0) 
    
    pdf.set_font('Arial', '', 9)
    col_w = 45
    for key, value in metrics.items():
        pdf.cell(col_w, 10, f"{key}", 1, 0, 'C')
    pdf.ln()
    pdf.set_font('Arial', 'B', 10)
    for key, value in metrics.items():
        pdf.cell(col_w, 10, f"{value}", 1, 0, 'C')
    pdf.ln(15)

    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(0, 39, 118)
    pdf.cell(0, 10, 'Gráficos de Projeção', 0, 1)
    pdf.set_text_color(0, 0, 0)
    
    try:
        with tempfile.TemporaryDirectory() as tmpdirname:
            for i, fig in enumerate(figures):
                if fig:
                    fig.update_layout(template="plotly_white", paper_bgcolor="white", plot_bgcolor="white", font=dict(color="black"))
                    img_path = os.path.join(tmpdirname, f"chart_cen_{i}.png")
                    fig.write_image(img_path, width=800, height=400, scale=2)
                    
                    if pdf.get_y() > 220:
                        pdf.add_page()
                    
                    pdf.image(img_path, x=10, w=190)
                    pdf.ln(5)
    except Exception as e: pass

    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(0, 39, 118)
    pdf.cell(0, 10, 'Colaboradores Afetados', 0, 1)
    pdf.set_text_color(0, 0, 0)
    
    pdf.set_font('Arial', 'B', 7)
    cols = ['Nome', 'Empresa', 'Pagar Total', 'Mensalidade', 'Dias Off']
    w_cols = [60, 50, 25, 25, 20]
    
    for i, c in enumerate(cols):
        pdf.cell(w_cols[i], 7, c, 1, 0, 'C')
    pdf.ln()
    
    pdf.set_font('Arial', '', 7)
    df_top = df.head(60) 
    
    for _, row in df_top.iterrows():
        try:
            pdf.cell(w_cols[0], 6, str(row['Nome'])[:35], 1)
            pdf.cell(w_cols[1], 6, str(row['Empresa'])[:30], 1)
            pdf.cell(w_cols[2], 6, f"R$ {row['Pagar']:,.2f}", 1, 0, 'R')
            pdf.cell(w_cols[3], 6, f"R$ {row['Mensal']:,.2f}", 1, 0, 'R')
            pdf.cell(w_cols[4], 6, f"{row['Dias']:.1f}", 1, 0, 'C')
            pdf.ln()
        except: pass

    return pdf.output(dest='S').encode('latin-1')

# --- GERADOR DE EXCEL INTELIGENTE ---
def gerar_excel_personalizado(df, titulo_planilha="Base de Dados"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=titulo_planilha)
        workbook = writer.book
        worksheet = writer.sheets[titulo_planilha]
        
        money_fmt = workbook.add_format({'num_format': 'R$ #,##0.00'})
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#002776', 'font_color': 'white', 'border': 1})
        
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_fmt)
            worksheet.set_column(col_num, col_num, 20)
            
            # Formata dinamicamente colunas que representam dinheiro
            nome_coluna = str(value).lower()
            if '(r$)' in nome_coluna or 'pagar' in nome_coluna or 'mensal' in nome_coluna:
                worksheet.set_column(col_num, col_num, 15, money_fmt)

        worksheet_capa = workbook.add_worksheet('Resumo')
        worksheet_capa.write('A1', f"Relatório: {titulo_planilha}")
        worksheet_capa.write('A2', f"Gerado em: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}")
        try:
            worksheet_capa.insert_image('A4', 'logo-brasil-digital.png', {'x_scale': 0.5, 'y_scale': 0.5})
        except: pass
        
    return output.getvalue()
